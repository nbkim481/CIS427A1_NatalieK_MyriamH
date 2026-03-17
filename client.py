import socket
import sys
import threading

SERVER_PORT = 5432
RECV_SIZE = 4096


def recv_loop(sock, stop_event):
    """Receive messages from the server and print them."""
    try:
        while not stop_event.is_set():
            data = sock.recv(RECV_SIZE)
            if not data:
                print("[server disconnected]")
                stop_event.set()
                break
            sys.stdout.write(data.decode("utf-8", errors="replace"))
            sys.stdout.flush()
    except Exception:
        stop_event.set()


def main():
    if len(sys.argv) != 2:
        print("usage: simplex-talk host", file=sys.stderr)
        sys.exit(1)

    host = sys.argv[1]

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except socket.error as e:
        print(f"simplex-talk: socket error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        s.connect((host, SERVER_PORT))
    except socket.gaierror:
        print(f"simplex-talk: unknown host: {host}", file=sys.stderr)
        sys.exit(1)
    except socket.error as e:
        print(f"simplex-talk: connect error: {e}", file=sys.stderr)
        s.close()
        sys.exit(1)

    print("Successfully connected to server!!")
    print("Enter commands (LOGIN, LOGOUT, WHO, LIST, BALANCE, LOOKUP, BUY, SELL, DEPOSIT, SHUTDOWN, QUIT)")

    stop_event = threading.Event()
    receiver = threading.Thread(target=recv_loop, args=(s, stop_event), daemon=True)
    receiver.start()

    try:
        for line in sys.stdin:
            if stop_event.is_set():
                break

            if not line.endswith("\n"):
                line += "\n"

            try:
                s.sendall(line.encode("utf-8"))
            except socket.error as e:
                print(f"simplex-talk: send error: {e}", file=sys.stderr)
                break

            cmd = line.strip().upper().split()[0] if line.strip() else ""
            if cmd in ("QUIT", "SHUTDOWN"):
                break

    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        try:
            s.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        s.close()


if __name__ == "__main__":
    main()
