import socket
import threading
import json
import time
import sys
import random

# Endereço e portas do servidor
SERVER_HOST = 'server'  
TCP_PORT = 9000
UDP_PORT = 9001

# Função para enviar mensagens em JSON pelo socket TCP
def send_json(sock, obj):
    data = json.dumps(obj).encode('utf-8')
    sock.sendall(len(data).to_bytes(4, 'big') + data)

# Função para receber mensagens em JSON pelo socket TCP
def recv_json(sock):
    header = sock.recv(4)
    if not header:
        raise ConnectionError("closed")
    size = int.from_bytes(header, 'big')
    data = b''
    while len(data) < size:
        part = sock.recv(size - len(data))
        if not part:
            raise ConnectionError("closed")
        data += part
    return json.loads(data.decode('utf-8'))

# Função de entrada do usuário com tempo limite (timeout)
def input_with_timeout(prompt, timeout):
    if sys.platform == "win32":  # Implementação para Windows
        import msvcrt
        sys.stdout.write(prompt)
        sys.stdout.flush()
        end = time.time() + timeout
        s = ""
        while time.time() < end:
            if msvcrt.kbhit():
                ch = msvcrt.getwche()
                if ch in ("\r", "\n"):
                    print("")
                    return s
                elif ch == "\003":  
                    raise KeyboardInterrupt
                elif ch == "\b":
                    s = s[:-1]
                    sys.stdout.write("\b \b")
                else:
                    s += ch
            time.sleep(0.01)
        return None
    else:  # Implementação para Linux/macOS
        import select
        sys.stdout.write(prompt)
        sys.stdout.flush()
        r, _, _ = select.select([sys.stdin], [], [], timeout)
        if r:
            line = sys.stdin.readline()
            if not line:
                return None
            return line.rstrip("\n")
        return None

# Função para calcular o tempo de resposta via UDP (ping)
def udp_ping(server_ip):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(2.0)
    try:
        ts = time.time()
        payload = ("ping:%f" % ts).encode('utf-8')
        s.sendto(payload, (server_ip, UDP_PORT))
        data, _ = s.recvfrom(4096)
        now = time.time()
        sent_t = float(data.decode('utf-8').split(":")[1])
        rtt = (now - sent_t) * 1000.0
        return rtt
    except Exception:
        return None

# Menu interativo para o usuário
def interactive_menu(tcp_sock, server_ip):
    while True:
        print("\n=== MENU ===")
        print("1 - Jogar")
        print("2 - Abrir pacote")
        print("3 - Equipar skins")
        print("4 - Sair")
        choice = input("Escolha: ").strip()

        # Entrar na fila de jogo
        if choice == "1":
            send_json(tcp_sock, {"cmd": "join_queue"})
            print("Entrou na fila. Aguardando adversário...")
            game_loop(tcp_sock)

        # Abrir pacotes de skins
        elif choice == "2":
            print("Solicitando abrir pacote...")
            send_json(tcp_sock, {"cmd": "open_package"})
            resp = recv_json(tcp_sock)
            if resp.get("cmd") == "package_opened":
                print("Você ganhou as skins:")
                for p in resp["awarded"]:
                    print(" -", p["type"], ":", p["skin"])
            else:
                print("Resposta:", resp)

        # Equipar skins
        elif choice == "3":
            send_json(tcp_sock, {"cmd": "list_skins"})
            resp = recv_json(tcp_sock)
            if resp.get("cmd") == "skins_list":
                owned = resp.get("owned", [])
                equipped = resp.get("equipped", {})
                print("\n=== Suas Skins ===")
                if not owned:
                    print("Você não possui skins.")
                    continue
                for i, p in enumerate(owned, 1):
                    print(f"{i}. {p['type']} - {p['skin']}")
                print("Equipada atualmente:", equipped)
                s = input("Escolha o número da skin (0 para cancelar): ").strip()
                try:
                    n = int(s)
                    if n == 0:
                        print("Operação cancelada.")
                        continue
                    if 1 <= n <= len(owned):
                        sel = owned[n - 1]
                        send_json(tcp_sock, {"cmd": "equip", "type": sel["type"], "skin": sel["skin"]})
                        resp2 = recv_json(tcp_sock)
                        print("Resposta do servidor:", resp2)
                    else:
                        print("Número fora do intervalo. Operação cancelada.")
                except Exception:
                    print("Entrada inválida. Operação cancelada.")
            else:
                print("Resposta inesperada:", resp)

        # Sair do jogo
        elif choice == "4":
            print("Saindo...")
            tcp_sock.close()
            sys.exit(0)

        else:
            print("Opção inválida")

# Função principal do loop de jogo
def game_loop(tcp_sock):
    try:
        while True:
            msg = recv_json(tcp_sock)
            cmd = msg.get("cmd")

            # Jogador entrou na fila
            if cmd == "queued":
                pass

            # Início da partida
            elif cmd == "game_start":
                print("[GAME] partida iniciada contra", msg.get("opponent"))
                hand = msg.get("hand", [])
                print("Sua mão inicial:", hand)

            # Início de um turno
            elif cmd == "turn_start":
                hand = msg.get("hand", [])
                print(f"\n[TURN] Turno {msg.get('turn')}. Sua mão:")
                if hand:
                    for i, c in enumerate(hand, start=1):
                        print(f" {i}. {c}")
                    prompt = f"Escolha o número da carta (1-{len(hand)}): "
                else:
                    print(" (sem cartas na mão)")
                    prompt = "Sem cartas: escolha será aleatória. Pressione Enter ou aguarde: "

                user_choice = input_with_timeout(prompt, 10)
                chosen_card = None

                # Caso o jogador não escolha, o sistema decide automaticamente
                if user_choice is None or user_choice.strip() == "":
                    if hand:
                        idx = random.randrange(len(hand))
                        chosen_card = hand.pop(idx)
                        print("Sem escolha. Carta aleatória:", chosen_card)
                    else:
                        chosen_card = random.choice(["Pedra", "Papel", "Tesoura"])
                        print("Sem cartas. Escolhida aleatoriamente:", chosen_card)
                else:
                    try:
                        n = int(user_choice.strip())
                        if 1 <= n <= len(hand):
                            chosen_card = hand.pop(n - 1)
                            print("Você jogou:", chosen_card)
                        else:
                            if hand:
                                idx = random.randrange(len(hand))
                                chosen_card = hand.pop(idx)
                                print("Número inválido. Carta aleatória:", chosen_card)
                            else:
                                chosen_card = random.choice(["Pedra", "Papel", "Tesoura"])
                                print("Número inválido. Carta aleatória:", chosen_card)
                    except Exception:
                        if hand:
                            idx = random.randrange(len(hand))
                            chosen_card = hand.pop(idx)
                            print("Entrada inválida. Carta aleatória:", chosen_card)
                        else:
                            chosen_card = random.choice(["Pedra", "Papel", "Tesoura"])
                            print("Entrada inválida. Carta aleatória:", chosen_card)

                send_json(tcp_sock, {"cmd": "play", "card": chosen_card, "skin": None})

            # Resultado de um turno
            elif cmd == "turn_result":
                print(f"[RESULT] Você jogou {msg['your_card']} | Oponente jogou {msg['opp_card']}")
                print(f"Vidas - você: {msg['your_lives']} | oponente: {msg['opp_lives']}")
                rtt = udp_ping(SERVER_HOST)
                if rtt is not None:
                    print(f"[PING] RTT = {rtt:.1f} ms")
                else:
                    print("[PING] falhou")

            # Fim da partida
            elif cmd == "game_over":
                print("[GAME OVER]", msg.get("result"))
                break

            # Oponente desconectou
            elif cmd == "opponent_disconnect":
                print("[GAME] adversário desconectou. Vitória.")
                break

            # Mensagens genéricas
            else:
                print("[INFO]", msg)

    except Exception as e:
        print("[GAME] conexão perdida:", e)

# Função principal do cliente
if __name__ == "__main__":
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.connect((SERVER_HOST, TCP_PORT))
    print("Conectado ao servidor TCP", SERVER_HOST, TCP_PORT)
    interactive_menu(tcp, SERVER_HOST)
