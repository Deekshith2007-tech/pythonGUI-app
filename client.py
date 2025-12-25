import socket
import threading
import os
import time
import json
from datetime import datetime

# Global config
HOST = os.environ.get("CHAT_HOST", "127.0.0.1")
PORT = int(os.environ.get("CHAT_PORT", "5000"))
OFFLINE_QUEUE_FILE = "offline_messages.json"


class ChatClient:
    """Thread-safe chat client with offline message support."""
    
    def __init__(self, username):
        self.username = username
        self._sock = None
        self._sock_lock = threading.Lock()
    
    def _load_offline_queue(self):
        """Load offline message queue from file."""
        if os.path.exists(OFFLINE_QUEUE_FILE):
            try:
                with open(OFFLINE_QUEUE_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_offline_queue(self, queue):
        """Save offline message queue to file."""
        try:
            with open(OFFLINE_QUEUE_FILE, 'w') as f:
                json.dump(queue, f, indent=2)
        except Exception:
            pass
    
    def _add_offline_message(self, to_user, message):
        """Queue a message for offline delivery."""
        queue = self._load_offline_queue()
        if to_user not in queue:
            queue[to_user] = []
        queue[to_user].append({
            "from": self.username,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })
        self._save_offline_queue(queue)
    
    def _get_pending_messages(self):
        """Get and clear pending offline messages for this user."""
        queue = self._load_offline_queue()
        messages = queue.pop(self.username, [])
        self._save_offline_queue(queue)
        return messages
    
    def _create_socket(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s
    
    def connect(self, retries=3, delay=1.0):
        """Try to connect to the server. Returns True on success."""
        with self._sock_lock:
            if self._sock:
                return True
            
            for attempt in range(retries):
                try:
                    s = self._create_socket()
                    s.connect((HOST, PORT))
                    self._sock = s
                    # Send /name command
                    s.sendall(f"/name {self.username}".encode("utf-8"))
                    return True
                except Exception:
                    try:
                        s.close()
                    except Exception:
                        pass
                    time.sleep(delay)
            return False
    
    def receive(self, callback):
        """Blocking receive loop. Intended to be run in a thread."""
        # Try to connect if not already connected
        if not self._sock:
            if not self.connect(retries=5, delay=1.0):
                try:
                    callback("ERROR: could not connect to server")
                except Exception:
                    pass
                return
        
        # Deliver any pending offline messages first
        pending = self._get_pending_messages()
        for msg_data in pending:
            try:
                callback(f"{msg_data['from']}: {msg_data['message']}")
            except Exception:
                pass
        
        # Now receive live messages
        try:
            while True:
                data = self._sock.recv(4096)
                if not data:
                    break
                text = data.decode("utf-8").strip()
                if not text:
                    continue
                if text == "/exit_ack":
                    try:
                        self._sock.close()
                    except Exception:
                        pass
                    break
                try:
                    callback(text)
                except Exception as e:
                    pass
        except Exception as e:
            pass
    
    def send(self, message, to_user=None):
        """Send a message. If server unreachable, queue for offline delivery."""
        # If not connected and we have recipient info, queue for offline
        if not self._sock and to_user:
            self._add_offline_message(to_user, message)
            return True
        
        # Try to connect if needed
        if not self._sock:
            if not self.connect():
                if to_user:
                    self._add_offline_message(to_user, message)
                return False
        
        try:
            self._sock.sendall(message.encode("utf-8"))
            return True
        except Exception:
            # On send failure, queue if we have recipient info
            if to_user:
                self._add_offline_message(to_user, message)
            return False
    
    def close(self):
        """Close the connection."""
        with self._sock_lock:
            if self._sock:
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = None


# Global client instances (one per username)
_clients = {}
_clients_lock = threading.Lock()


def _get_client(username):
    """Get or create a client instance for a username."""
    global _clients
    with _clients_lock:
        if username not in _clients:
            _clients[username] = ChatClient(username)
        return _clients[username]


def connect(username, retries=3, delay=1.0):
    """Connect a client with the given username."""
    client = _get_client(username)
    return client.connect(retries, delay)


def receive(callback, username=None):
    """Receive messages (requires prior connect call with same username)."""
    # Get username from the current client context
    if username is None:
        global _clients
        if not _clients:
            username = "Anonymous"
        else:
            username = list(_clients.keys())[0]
    
    client = _get_client(username)
    client.receive(callback)


def send(message, to_user=None, username=None):
    """Send a message from a client."""
    if username is None:
        global _clients
        if not _clients:
            username = "Anonymous"
        else:
            username = list(_clients.keys())[0]
    
    client = _get_client(username)
    return client.send(message, to_user)


def close(username=None):
    """Close a client connection."""
    if username is None:
        global _clients
        for client in _clients.values():
            client.close()
    else:
        if username in _clients:
            _clients[username].close()


if __name__ == "__main__":
    username = input("Enter your username: ").strip() or "Anonymous"
    if connect(username):
        try:
            threading.Thread(target=receive, args=(print, username), daemon=True).start()
            while True:
                msg = input()
                send(msg, username=username)
                if msg == "/exit":
                    break
        finally:
            close(username)
    else:
        print("Could not connect to server.")