import socket, json, threading, time, os, csv
import urllib.request

RYU = "http://127.0.0.1:8080"
DPID = 1
CAP = 10  # Mbps per host link
PORTS = {"10.0.0.1": 1, "10.0.0.2": 2, "10.0.0.3": 3}
lock = threading.Lock()
res = {}
next_id = 1
stats = {"accepted": 0, "rejected": 0}
os.makedirs("results", exist_ok=True)

def ryu(path, body):
    req = urllib.request.Request(RYU + path, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    try:
        return urllib.request.urlopen(req, timeout=3).status == 200
    except Exception as e:
        print("controller error:", e)
        return False

def flow(r):
    return {"dpid": DPID, "priority": 100,
            "match": {"eth_type": 2048, "ipv4_src": r["src"], "ipv4_dst": r["dst"]},
            "actions": [{"type": "METER", "meter_id": r["id"]},
                        {"type": "OUTPUT", "port": PORTS[r["dst"]]}]}

def install(r):
    kbps = int(r["bw"] * 1000)
    if not ryu("/stats/meterentry/add", {"dpid": DPID, "meter_id": r["id"], "flags": "KBPS",
            "bands": [{"type": "DROP", "rate": kbps, "burst_size": max(100, kbps // 2)}]}):
        return False
    if not ryu("/stats/flowentry/add", flow(r)):
        ryu("/stats/meterentry/delete", {"dpid": DPID, "meter_id": r["id"]})
        return False
    return True

def remove(r):
    ryu("/stats/flowentry/delete_strict", flow(r))
    ryu("/stats/meterentry/delete", {"dpid": DPID, "meter_id": r["id"]})

def load(ip):
    return sum(r["bw"] for r in res.values() if ip in (r["src"], r["dst"]))

def log(event, r=None):
    with open("results/log.csv", "a", newline="") as f:
        csv.writer(f).writerow([round(time.time(), 2), event, r["id"] if r else "",
            r["src"] if r else "", r["dst"] if r else "", r["bw"] if r else "",
            sum(r2["bw"] for r2 in res.values()), stats["accepted"], stats["rejected"]])
    print(event, r["id"] if r else "", "| active:", len(res), stats)

def reject(reason):
    stats["rejected"] += 1
    log("REJECTED:" + reason)
    return {"status": "REJECTED", "reason": reason}

def process(q):
    global next_id
    t = q.get("type")
    with lock:
        if t == "RESERVE":
            try:
                src, dst = q["src"], q["dst"]
                bw, dur = float(q["bw"]), float(q["duration"])
            except Exception:
                return reject("invalid request")
            if src not in PORTS or dst not in PORTS or src == dst or bw <= 0 or dur <= 0:
                return reject("invalid request")
            if any(r["src"] == src and r["dst"] == dst for r in res.values()):
                return reject("conflict: reservation already exists")
            if load(src) + bw > CAP or load(dst) + bw > CAP:
                return reject("insufficient capacity")
            r = {"id": next_id, "src": src, "dst": dst, "bw": bw, "expires": time.time() + dur}
            if not install(r):
                return reject("controller error")
            next_id += 1
            res[r["id"]] = r
            stats["accepted"] += 1
            log("ACCEPTED", r)
            return {"status": "ACCEPTED", "id": r["id"], "expires_in": dur}
        if t == "CANCEL":
            r = res.pop(q.get("id"), None)
            if not r:
                return {"status": "ERROR", "reason": "unknown id"}
            remove(r)
            log("CANCELLED", r)
            return {"status": "CANCELLED", "id": r["id"]}
        if t == "QUERY":
            return {"status": "OK", "active": list(res.values()), "stats": stats,
                    "utilization_pct": {ip: 100 * load(ip) / CAP for ip in PORTS}}
        return {"status": "ERROR", "reason": "unknown type"}

def expiry():
    while True:
        time.sleep(1)
        with lock:
            for rid, r in list(res.items()):
                if time.time() >= r["expires"]:
                    remove(r)
                    del res[rid]
                    log("EXPIRED", r)

def handle(conn):
    with conn:
        try:
            q = json.loads(conn.makefile().readline())
        except Exception:
            q = {}
        conn.sendall((json.dumps(process(q)) + "\n").encode())

threading.Thread(target=expiry, daemon=True).start()
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", 5000))
s.listen()
print("reservation server on 5000")
while True:
    c, _ = s.accept()
    threading.Thread(target=handle, args=(c,), daemon=True).start()
