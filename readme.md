
# 🃏 Jogo Pedra, Papel e Tesoura Online (Cliente-Servidor)

Este projeto implementa um sistema **cliente-servidor** para um jogo online de **Pedra, Papel e Tesoura (RPS)** com skins, pacotes e partidas em tempo real.  
Foi desenvolvido inteiramente por [Edgardem](https://github.com/Edgardem) em **Python 3.11** e usa **Docker** para facilitar a execução e testes.

---

## 🚀 Funcionalidades

- **Servidor TCP/UDP** para gerenciar jogadores, partidas e medições de latência.  
- **Matchmaking automático**: jogadores são pareados em duelos 1x1.  
- **Sistema de pacotes**: jogadores podem abrir pacotes para ganhar skins de cartas.  
- **Customização**: jogadores podem equipar skins nas cartas (Pedra, Papel ou Tesoura).  
- **Batalhas em turnos**: cada jogador recebe um baralho e joga até alguém perder todas as vidas.  
- **Teste de estresse**: script para simular múltiplos jogadores concorrentes.

---

## 📂 Estrutura do Projeto

├── server.py             # Servidor TCP/UDP principal <br> 
├── client.py             # Cliente interativo para jogar <br>
├── stress\_test.py        # Teste automático de estresse <br>
├── Dockerfile.server     # Dockerfile do servidor <br>
├── Dockerfile.client     # Dockerfile do cliente <br>
└── docker-compose.yml    # Orquestração com múltiplos clientes + servidor <br>

---

## 🐳 Executando com Docker

### 1. Subir o ambiente com servidor e múltiplos clientes
```bash
docker-compose up --build
````

Isso iniciará:

* `rps_server` → servidor escutando nas portas **9000 (TCP)** e **9001 (UDP)**
* `rps_client1` até `rps_client6` → instâncias de clientes interativos

### 2. Acessar um cliente

Abra outro terminal e execute:

```bash
docker exec -it rps_client1 bash
python client.py
```

---

## 🕹️ Como Jogar

Ao rodar o cliente, um **menu interativo** aparece:

1. **Jogar** → entra na fila e aguarda o pareamento.
2. **Abrir pacote** → solicita skins novas aleatórias.
3. **Equipar skins** → aplica skins ganhas em suas cartas.
4. **Sair** → encerra o cliente.

Durante a partida:

* Cada jogador começa com **3 vidas**.
* As jogadas são feitas em turnos com limite de tempo.
* Caso não jogue, o sistema escolhe uma carta automaticamente.
* Vence quem zerar as vidas do oponente.

---

## 🧪 Testes de Estresse

O arquivo `stress_test.py` permite simular múltiplos clientes para verificar:

* **Concorrência** no servidor
* **Estabilidade** com diversos jogadores simultâneos
* **Desempenho** em partidas rápidas

Executar manualmente:


python stress_test.py

---

## ⚙️ Tecnologias Utilizadas

* **Python 3.11**
* **Visual Studio Code** 
* **Sockets TCP/UDP** para comunicação
* **Threading** para concorrência
* **Docker e Docker Compose** para execução e orquestração

---

## 📜 Autor

Projeto desenvolvido por **Edgar Rocha**

* GitHub: [Edgardem](https://github.com/Edgardem)
* E-mail: [akhilhakai@gmail.com](mailto:akhilhakai@gmail.com)

---
