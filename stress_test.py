import socket
import json
import threading
import time

SERVER_HOST = "127.0.0.1"   # ou "server" no Docker
TCP_PORT = 9000

def send_json(sock, obj):
    data = json.dumps(obj).encode('utf-8')
    sock.sendall(len(data).to_bytes(4,'big') + data)

def recv_json(sock):
    header = sock.recv(4)
    if not header:
        raise ConnectionError("closed")
    size = int.from_bytes(header,'big')
    data = b''
    while len(data) < size:
        part = sock.recv(size - len(data))
        if not part:
            raise ConnectionError("closed")
        data += part
    return json.loads(data.decode('utf-8'))

def client_worker(i, results):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((SERVER_HOST, TCP_PORT))
        send_json(s, {"cmd":"open_package"})
        resp = recv_json(s)
        results[i] = resp
        s.close()
    except Exception as e:
        results[i] = {"error": str(e)}

def stress_test(num_clients=50):
    threads = []
    results = {}
    for i in range(num_clients):
        t = threading.Thread(target=client_worker, args=(i, results))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    # Estatísticas
    ok = sum(1 for r in results.values() if r.get("cmd") == "package_opened")
    empty = sum(1 for r in results.values() if r.get("cmd") == "package_empty")
    errors = [r for r in results.values() if "error" in r]

    print(f"Total de clientes: {num_clients}")
    print(f"Pacotes abertos com sucesso: {ok}")
    print(f"Pacotes recusados (estoque vazio): {empty}")
    print(f"Erros: {len(errors)}")
    if errors:
        print("Exemplos de erros:", errors[:3])

if __name__ == "__main__":
    stress_test(50)  # tenta 50 clientes em paralelo
