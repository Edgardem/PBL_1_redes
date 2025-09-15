#!/usr/bin/env python3
import socket
import threading
import json
import random
import time
from collections import deque
from queue import Queue, Empty

# Endereço e portas do servidor
HOST = '0.0.0.0'
TCP_PORT = 9000
UDP_PORT = 9001

# Conjunto de skins possíveis para cada tipo de carta
SKINS = {
    "Pedra": [
        "Rochedo Ancestral","Magma Vivo","Cristal Celeste","Pedra Filosofal",
        "Meteorito Caído","Granito Dourado","Golem de Obsidiana","Pedra Rúnica"
    ],
    "Papel": [
        "Pergaminho Arcano","Carta Real","Contrato Sombrio","Origami de Dragão",
        "Mapa do Tesouro","Folha Dourada","Diário Proibido","Manuscrito Eterno"
    ],
    "Tesoura": [
        "Lâmina Fantasma","Corte Celestial","Foice Lunar","Tesoura de Ferro Forjado",
        "Cortante de Cristal","Garras Flamejantes","Navalha Sombria","Tesoura Samurai"
    ]
}

# Estruturas globais de controle
match_queue = deque()                  # fila de jogadores aguardando partida
match_lock = threading.Lock()

package_queue = deque()                # fila de pedidos de pacotes (client_id, evento)
package_lock = threading.Lock()
PACKAGE_STOCK = 20                     # estoque máximo de pacotes disponíveis

clients_lock = threading.Lock()
clients = {}                           # dicionário com informações de cada cliente conectado

# Função para enviar mensagens em JSON pelo socket
def send_json(sock, obj):
    data = json.dumps(obj).encode('utf-8')
    sock.sendall(len(data).to_bytes(4,'big') + data)

# Função para receber mensagens em JSON pelo socket
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

# Servidor UDP usado para medir latência (ping-pong)
def udp_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((HOST, UDP_PORT))
    print(f"[UDP] ping server listening {HOST}:{UDP_PORT}")
    while True:
        data, addr = s.recvfrom(4096)
        s.sendto(data, addr)

# Monitor de matchmaking: verifica a fila de jogadores e inicia partidas
def matchmaking_watcher():
    while True:
        with match_lock:
            if len(match_queue) >= 2:
                a = match_queue.popleft()
                b = match_queue.popleft()
            else:
                a = b = None
        if a and b:
            with clients_lock:
                if a in clients and b in clients:
                    clients[a]['in_game'] = True
                    clients[b]['in_game'] = True
                    clients[a]['game_queue'] = Queue()
                    clients[b]['game_queue'] = Queue()
                    threading.Thread(target=game_session, args=(a,b), daemon=True).start()
                else:
                    # Se um desconectou, devolve o outro para a fila
                    if a in clients:
                        with match_lock:
                            match_queue.appendleft(a)
                    if b in clients:
                        with match_lock:
                            match_queue.appendleft(b)
        else:
            time.sleep(0.1)

# Lógica principal da sessão de jogo entre dois jogadores
def game_session(cli_a, cli_b):
    print(f"[GAME] starting game between {cli_a} and {cli_b}")
    with clients_lock:
        A = clients.get(cli_a)
        B = clients.get(cli_b)
    if not A or not B:
        print("[GAME] abort, client missing")
        return
    sock_a = A['sock']; sock_b = B['sock']

    # Função para gerar baralho aleatório de 10 cartas
    def make_deck():
        deck = []
        for _ in range(10):
            deck.append(random.choice(["Pedra","Papel","Tesoura"]))
        random.shuffle(deck)
        return deck

    deck_a = make_deck()
    deck_b = make_deck()
    lives_a = 3; lives_b = 3
    turn = 1

    # Cada jogador começa com 3 cartas na mão
    hand_a = [deck_a.pop() for _ in range(min(3,len(deck_a)))]
    hand_b = [deck_b.pop() for _ in range(min(3,len(deck_b)))]

    # Monta mão de exibição (usa skin equipada ou tipo padrão)
    def build_display_hand(client_id, hand_types):
        with clients_lock:
            cl = clients.get(client_id)
            skins_map = cl['skins'] if cl else {}
        return [ skins_map.get(t, t) for t in hand_types ]

    # Traduz entrada do cliente (tipo ou nome de skin) para tipo
    def resolve_input_to_type(client_id, input_card):
        if not input_card:
            return None
        if input_card in ("Pedra","Papel","Tesoura"):
            return input_card
        with clients_lock:
            cl = clients.get(client_id)
            if not cl:
                return None
            for t, s in cl.get('skins', {}).items():
                if s == input_card:
                    return t
        return None

    # Envia mensagem inicial de início de jogo
    send_json(sock_a, {"cmd":"game_start","opponent":cli_b, "hand": build_display_hand(cli_a, hand_a), "lives":lives_a})
    send_json(sock_b, {"cmd":"game_start","opponent":cli_a, "hand": build_display_hand(cli_b, hand_b), "lives":lives_b})

    # Loop principal de turnos
    while True:
        if lives_a <= 0 or lives_b <= 0:
            break
        if not deck_a and not deck_b and not hand_a and not hand_b:
            break

        tid = f"turn-{cli_a}-{cli_b}-{turn}-{int(time.time())}"

        # Envia início de turno para os dois jogadores
        send_json(sock_a, {"cmd":"turn_start","turn":turn, "hand": build_display_hand(cli_a, hand_a), "tid":tid})
        send_json(sock_b, {"cmd":"turn_start","turn":turn, "hand": build_display_hand(cli_b, hand_b), "tid":tid})

        # Coleta jogada de cada jogador
        try:
            r1 = clients[cli_a]['game_queue'].get(timeout=25)
        except Exception:
            print("[GAME] timeout ou A desconectou")
            send_json(sock_b, {"cmd":"opponent_disconnect"})
            break
        try:
            r2 = clients[cli_b]['game_queue'].get(timeout=25)
        except Exception:
            print("[GAME] timeout ou B desconectou")
            send_json(sock_a, {"cmd":"opponent_disconnect"})
            break

        if not r1 or not r2:
            print("[GAME] got empty play payload")
            break
        if r1.get("cmd") != "play" or r2.get("cmd") != "play":
            print("[GAME] unexpected payloads", r1, r2)
            break

        # Entrada dos jogadores
        in_a = r1.get("card")
        in_b = r2.get("card")

        # Resolve entrada para tipo
        type_a = resolve_input_to_type(cli_a, in_a)
        type_b = resolve_input_to_type(cli_b, in_b)

        # Caso inválido: escolhe fallback (aleatório da mão ou aleatório geral)
        if not type_a:
            if hand_a:
                idx = random.randrange(len(hand_a))
                type_a = hand_a.pop(idx)
            else:
                type_a = random.choice(["Pedra","Papel","Tesoura"])
        else:
            try:
                hand_a.remove(type_a)
            except ValueError:
                if hand_a:
                    idx = random.randrange(len(hand_a))
                    type_a = hand_a.pop(idx)
                else:
                    type_a = random.choice(["Pedra","Papel","Tesoura"])

        if not type_b:
            if hand_b:
                idx = random.randrange(len(hand_b))
                type_b = hand_b.pop(idx)
            else:
                type_b = random.choice(["Pedra","Papel","Tesoura"])
        else:
            try:
                hand_b.remove(type_b)
            except ValueError:
                if hand_b:
                    idx = random.randrange(len(hand_b))
                    type_b = hand_b.pop(idx)
                else:
                    type_b = random.choice(["Pedra","Papel","Tesoura"])

        # Resolve vencedor
        with clients_lock:
            sk_a = clients.get(cli_a, {}).get('skins', {}).get(type_a, type_a)
            sk_b = clients.get(cli_b, {}).get('skins', {}).get(type_b, type_b)

        winner = None
        if type_a != type_b:
            if (type_a=="Pedra" and type_b=="Tesoura") or \
               (type_a=="Tesoura" and type_b=="Papel") or \
               (type_a=="Papel" and type_b=="Pedra"):
                winner = 'A'
                lives_b -= 1
            else:
                winner = 'B'
                lives_a -= 1

        # Envia resultado do turno para ambos
        resA = {"cmd":"turn_result","your_card": sk_a,"your_card_type": type_a,
                "opp_card": sk_b,"opp_card_type": type_b,"winner": winner,
                "your_lives": lives_a,"opp_lives": lives_b}
        resB = {"cmd":"turn_result","your_card": sk_b,"your_card_type": type_b,
                "opp_card": sk_a,"opp_card_type": type_a,
                "winner": ('A' if winner=='B' else ('B' if winner=='A' else None)),
                "your_lives": lives_b,"opp_lives": lives_a}
        send_json(sock_a, resA)
        send_json(sock_b, resB)

        # Fase de compra de carta
        if deck_a:
            hand_a.append(deck_a.pop())
        if deck_b:
            hand_b.append(deck_b.pop())

        turn += 1
        time.sleep(0.05)

    # Define resultado final
    if lives_a <= 0 and lives_b <= 0:
        final = "tie"
    elif lives_a <= 0:
        final = f"{cli_b}_wins"
    elif lives_b <= 0:
        final = f"{cli_a}_wins"
    else:
        final = "tie"

    try:
        send_json(sock_a, {"cmd":"game_over","result":final})
    except Exception:
        pass
    try:
        send_json(sock_b, {"cmd":"game_over","result":final})
    except Exception:
        pass

    print(f"[GAME] finished {cli_a} vs {cli_b} -> {final}")

    # Limpeza do estado dos jogadores
    with clients_lock:
        if cli_a in clients:
            clients[cli_a]['in_game'] = False
            clients[cli_a]['game_queue'] = None
        if cli_b in clients:
            clients[cli_b]['in_game'] = False
            clients[cli_b]['game_queue'] = None

# Função para lidar com cada cliente conectado ao servidor TCP
def handle_client(conn, addr):
    client_id = f"{addr[0]}:{addr[1]}"
    print("[TCP] new", client_id)
    inbox = Queue()
    with clients_lock:
        clients[client_id] = {"sock":conn, "addr":addr, "skins":{}, "packages":[], "inbox": inbox, "game_queue": None, "in_game": False}

    global PACKAGE_STOCK

    # Thread leitora: recebe mensagens e coloca na fila inbox
    def reader():
        try:
            while True:
                msg = recv_json(conn)
                inbox.put(msg)
        except Exception as e:
            print("[READER] client reader ended", client_id, e)
        finally:
            inbox.put(None)

    threading.Thread(target=reader, daemon=True).start()

    try:
        while True:
            msg = inbox.get()
            if msg is None:
                break
            cmd = msg.get("cmd")
            if cmd == "join_queue":
                with match_lock:
                    match_queue.append(client_id)
                send_json(conn, {"cmd":"queued"})
            elif cmd == "open_package":
                event = threading.Event()
                queued = False
                with package_lock:
                    if PACKAGE_STOCK > 0:
                        PACKAGE_STOCK -= 1
                        package_queue.append((client_id,event))
                        queued = True
                        print(f"[PACKAGE] reserved for {client_id}, remaining stock {PACKAGE_STOCK}")
                if not queued:
                    send_json(conn, {"cmd":"package_empty","reason":"no_stock"})
                    continue
                event.wait()
                awarded = []
                for _ in range(3):
                    t = random.choice(["Pedra","Papel","Tesoura"])
                    s = random.choice(SKINS[t])
                    awarded.append({"type":t,"skin":s})
                with clients_lock:
                    if client_id in clients:
                        clients[client_id]["packages"].extend(awarded)
                        try:
                            send_json(conn, {"cmd":"package_opened","awarded":awarded})
                        except Exception:
                            pass
                    else:
                        print(f"[PACKAGE] client {client_id} disconnected before award delivery")
            elif cmd == "equip":
                t = msg.get("type"); s = msg.get("skin")
                with clients_lock:
                    if any(p['skin']==s for p in clients[client_id]["packages"]):
                        clients[client_id]["skins"][t] = s
                        send_json(conn, {"cmd":"equip_ok","type":t,"skin":s})
                    else:
                        send_json(conn, {"cmd":"equip_fail","reason":"skin_not_owned"})
            elif cmd == "ping_check":
                send_json(conn, {"cmd":"pong"})
            elif cmd == "list_skins":
                with clients_lock:
                    pkgs = clients[client_id]["packages"]
                    eq = clients[client_id]["skins"]
                send_json(conn, {"cmd":"skins_list","owned":pkgs,"equipped":eq})
            elif cmd == "play":
                with clients_lock:
                    cl = clients.get(client_id)
                if cl and cl.get("in_game") and cl.get("game_queue") is not None:
                    cl["game_queue"].put(msg)
                else:
                    send_json(conn, {"cmd":"unknown"})
            else:
                send_json(conn, {"cmd":"unknown"})
    except Exception as e:
        print("[TCP] client disconnected", client_id, e)
    finally:
        refunded = 0
        with package_lock:
            if package_queue:
                new_q = deque()
                while package_queue:
                    cid, ev = package_queue.popleft()
                    if cid == client_id:
                        refunded += 1
                        try:
                            ev.set()
                        except Exception:
                            pass
                    else:
                        new_q.append((cid, ev))
                package_queue.extend(new_q)
                if refunded:
                    PACKAGE_STOCK += refunded
                    print(f"[PACKAGE] refunded {refunded} packages from disconnected {client_id}, stock={PACKAGE_STOCK}")

        with clients_lock:
            clients.pop(client_id, None)
        conn.close()

# Worker para processar pedidos de pacotes
def package_service():
    while True:
        with package_lock:
            if package_queue:
                client_id, event = package_queue.popleft()
            else:
                client_id = None
        if client_id:
            time.sleep(0.2)
            try:
                event.set()
            except Exception:
                pass
        else:
            time.sleep(0.1)

# Servidor TCP principal
def tcp_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, TCP_PORT))
    s.listen(128)
    print(f"[TCP] server listening {HOST}:{TCP_PORT}")
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn,addr), daemon=True).start()

# Inicialização: cria threads auxiliares e inicia o servidor TCP
if __name__ == "__main__":
    threading.Thread(target=udp_server, daemon=True).start()
    threading.Thread(target=matchmaking_watcher, daemon=True).start()
    threading.Thread(target=package_service, daemon=True).start()
    tcp_server()
