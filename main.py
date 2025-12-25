import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import traceback
from client import send, receive, connect


clients = {}


def create_client_ui(root, username):
    win = tk.Toplevel(root)
    win.title(f"Chat Client - {username}")
    win.geometry("500x400")

    chat_box = tk.Text(win, height=20, width=50)
    chat_box.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

    frame = tk.Frame(win)
    frame.pack(pady=5, padx=10, fill=tk.X)

    entry = tk.Entry(frame, width=40)
    entry.pack(side=tk.LEFT, padx=5)

    def send_message():
        msg = entry.get()
        if not msg.strip():
            return
        # Show local message immediately
        chat_box.insert(tk.END, f"You: {msg}\n")
        chat_box.see(tk.END)
        entry.delete(0, tk.END)
        # Send to server
        send(msg, to_user=None, username=username)

    send_button = tk.Button(frame, text="Send", command=send_message)
    send_button.pack(side=tk.LEFT)

    # Thread-safe show_message using root.after
    def _show_message(message):
        if message:
            chat_box.insert(tk.END, message + "\n")
            chat_box.see(tk.END)
            # also log to file for debugging
            try:
                with open('main.log', 'a', encoding='utf-8') as f:
                    f.write(f"[{username}] {message}\n")
            except Exception:
                pass

    def show_message_threadsafe(message):
        try:
            root.after(0, _show_message, message)
        except Exception:
            pass

    # Start receiving in background thread
    def start_client_listener():
        try:
            connect(username)
            time.sleep(0.2)
            threading.Thread(target=receive, args=(show_message_threadsafe, username), daemon=True).start()
        except Exception as e:
            show_message_threadsafe(f"ERROR: {e}")

    entry.bind('<Return>', lambda e: send_message())

    clients[username] = {
        'win': win,
        'chat_box': chat_box,
        'entry': entry,
        'start': start_client_listener
    }

    return win


def main():
    root = tk.Tk()
    root.withdraw()  # hide main root window

    # Create two client windows and start their listeners
    alice = create_client_ui(root, 'alice')
    bob = create_client_ui(root, 'bob')

    # Position windows
    alice.geometry('+50+50')
    bob.geometry('+600+50')

    # Start listeners after windows exist
    for c in clients.values():
        try:
            c['start']()
        except Exception:
            pass

    root.deiconify()  # make root exist so after callbacks work
    root.mainloop()


if __name__ == '__main__':
    main()