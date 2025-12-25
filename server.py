import socket
import threading
import datetime
import os

HOST = '0.0.0.0' 
PORT = 5000
LOG_DIR = 'chat_logs'

clients = {}
clients_lock = threading.Lock()

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

log_file_path = os.path.join(LOG_DIR, f"chat_log_{datetime.date.today().isoformat()}.txt")


def log(msg: str):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {msg}\n"
    print(line, end='')
    with open(log_file_path, 'a', encoding='utf-8') as f:
        f.write(line)


def broadcast(message: str, exclude_sock=None):
    """Send message to all connected clients except exclude_sock."""
    with clients_lock:
        for sock in list(clients.keys()):
            if sock is exclude_sock:
                continue
            try:
                sock.sendall(message.encode('utf-8'))
            except Exception:
                remove_client(sock)


def remove_client(sock):
    with clients_lock:
        username = clients.pop(sock, None)
    try:
        sock.close()
    except Exception:
        pass
    if username:
        log(f"{username} disconnected")
        broadcast(f"SERVER: {username} has left the chat.")


def handle_client(sock, addr):
    try:
        sock.sendall("SERVER: Send your name using /name YourName\n".encode('utf-8'))
        data = sock.recv(1024).decode('utf-8').strip()
        if data.startswith('/name'):
            username = data.partition(' ')[2].strip() or f"User{addr[1]}"
        else:
            username = f"User{addr[1]}"

        with clients_lock:
            clients[sock] = username

        log(f"{username} connected from {addr}")
        
        broadcast(f"SERVER: {username} has joined the chat.", exclude_sock=sock)
        sock.sendall(f"SERVER: Welcome {username}! Type /exit to leave.\n".encode('utf-8'))

        while True:
            data = sock.recv(4096)
            if not data:
                break
            text = data.decode('utf-8').strip()
            if not text:
                continue
            if text == '/exit':
                sock.sendall('/exit_ack'.encode('utf-8'))
                break
            log(f"{username}: {text}")
            broadcast(f"{username}: {text}", exclude_sock=sock)
    except Exception as e:
        log(f"Error with {addr}: {e}")
    finally:
        remove_client(sock)


def server_loop():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(20)
    log(f"Server listening on {HOST}:{PORT}")

    try:
        while True:
            sock, addr = s.accept()
            threading.Thread(target=handle_client, args=(sock, addr), daemon=True).start()
    except KeyboardInterrupt:
        log("Server shutting down...")
    finally:
        with clients_lock:
            for sock in list(clients.keys()):
                try:
                    sock.close()
                except:
                    pass
        s.close()


if __name__ == '__main__':
    server_loop()