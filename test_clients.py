import threading
import time
from client import connect, receive, send, close

msgs = {'alice': [], 'bob': []}

def make_cb(user):
    def cb(m):
        msgs[user].append(m)
        print(f"[{user}] RECV: {m}")
    return cb

# Connect both clients
print('Connecting alice...')
if not connect('alice'):
    print('Failed to connect alice')
else:
    threading.Thread(target=receive, args=(make_cb('alice'), 'alice'), daemon=True).start()

print('Connecting bob...')
if not connect('bob'):
    print('Failed to connect bob')
else:
    threading.Thread(target=receive, args=(make_cb('bob'), 'bob'), daemon=True).start()

# Give sockets time to settle
time.sleep(0.5)

# Exchange messages
print('alice -> hi')
send('hi', username='alice')

time.sleep(0.2)
print('bob -> hello')
send('hello', username='bob')

# Wait for deliveries
time.sleep(0.5)

print('\nFinal received lists:')
print('ALICE:', msgs['alice'])
print('BOB:  ', msgs['bob'])

# Cleanup
close('alice')
close('bob')
