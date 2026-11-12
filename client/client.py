import socket, json, sys
a = sys.argv[1:]
c = a[0].upper()
if c == "RESERVE":
    q = {"type": "RESERVE", "src": a[1], "dst": a[2], "bw": float(a[3]), "duration": float(a[4])}
elif c == "CANCEL":
    q = {"type": "CANCEL", "id": int(a[1])}
else:
    q = {"type": "QUERY"}
s = socket.create_connection(("10.123.123.1", 5000), timeout=5)
s.sendall((json.dumps(q) + "\n").encode())
print(s.makefile().readline())
