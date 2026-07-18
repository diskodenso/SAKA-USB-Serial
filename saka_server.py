import json
import serial
import threading
import time

from protocol import Cmd, Rsp, ALLOWED_CMDS, build_frame, parse_frames

SERIAL_PORT = "/dev/ttyGS0"
BAUD_RATE = 115200
VERSION_STR = "SAKA-v3-PoC"


class SakaServer:
    def __init__(self):
        self.ser = serial.Serial(
            SERIAL_PORT,
            BAUD_RATE,
            timeout=0.1
        )

        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

        self.buf = b""
        self.lock = threading.Lock()
        self.running = True

        self.peer_connected = False
        self.peer_id = None
        self.start_time = time.monotonic()

        print(
            f"[SAKA] Server gestartet auf {SERIAL_PORT} @ {BAUD_RATE}",
            flush=True
        )
        print(
            "[SAKA] Warte auf Smartphone-Verbindung...",
            flush=True
        )

    def _send_binary(self, rsp_type: int, payload: bytes = b"") -> None:
        with self.lock:
            frame = build_frame(rsp_type, payload)
            self.ser.write(frame)
            self.ser.flush()

    def _send_text(self, text: str) -> None:
        with self.lock:
            self.ser.write((text + "\r\n").encode("utf-8"))
            self.ser.flush()

    def _handle_text_command(self, chunk: bytes) -> bool:
        """
        Verarbeitet einfache Textbefehle für den Smartphone-Test.

        Rückgabewert:
        True  = Textbefehl wurde erkannt und verarbeitet
        False = Kein bekannter Textbefehl
        """

        try:
            text = chunk.decode("utf-8", errors="ignore").strip().upper()
        except Exception:
            return False

        if not text:
            return False

        if text == "PING":
            print("[SAKA] TEXT PING empfangen -> PONG", flush=True)
            self._send_text("PONG")
            return True

        if text == "STATUS":
            print("[SAKA] TEXT STATUS empfangen -> STATUS_OK", flush=True)

            status = {
                "status": "STATUS_OK",
                "version": VERSION_STR,
                "peer_connected": self.peer_connected,
                "peer_id": self.peer_id,
                "uptime_s": int(time.monotonic() - self.start_time),
                "interface": SERIAL_PORT,
                "ssh_required": False
            }

            self._send_text(json.dumps(status))
            return True

        if text == "HELP":
            print("[SAKA] TEXT HELP empfangen", flush=True)
            self._send_text("COMMANDS: PING, STATUS, HELP")
            return True

        return False

    def _handle_binary_command(
        self,
        cmd_type: int,
        payload: bytes
    ) -> None:

        if cmd_type not in ALLOWED_CMDS:
            self._send_binary(
                Rsp.REJECT,
                f"Unbekannter Befehl: 0x{cmd_type:02X}".encode()
            )
            return

        if cmd_type == Cmd.PING:
            print("[SAKA] BINARY PING empfangen -> PONG", flush=True)
            self._send_binary(Rsp.PONG)

        elif cmd_type == Cmd.STATUS:
            print(
                "[SAKA] BINARY STATUS empfangen -> STATUS_OK",
                flush=True
            )

            status = {
                "version": VERSION_STR,
                "peer_connected": self.peer_connected,
                "peer_id": self.peer_id,
                "uptime_s": int(time.monotonic() - self.start_time),
                "interface": SERIAL_PORT,
                "ssh_required": False
            }

            self._send_binary(
                Rsp.STATUS_OK,
                json.dumps(status).encode()
            )

        elif cmd_type == Cmd.SEND_MSG:
            if not self.peer_connected:
                self._send_binary(
                    Rsp.CONNECT_ERR,
                    b"Kein Peer verbunden"
                )
                return

            msg = payload.decode(errors="replace")
            print(f"[SAKA] SEND_MSG: {msg}", flush=True)
            self._send_binary(Rsp.MSG_SENT)

        elif cmd_type == Cmd.CONNECT:
            target = payload.decode(errors="replace").strip()

            self.peer_connected = True
            self.peer_id = target

            print(
                f"[SAKA] CONNECT simuliert zu: {target}",
                flush=True
            )

            self._send_binary(
                Rsp.CONNECT_OK,
                target.encode()[:32]
            )

        elif cmd_type == Cmd.DISCONNECT:
            self.peer_connected = False
            self.peer_id = None

            print("[SAKA] DISCONNECT", flush=True)
            self._send_binary(Rsp.PONG)

        elif cmd_type == Cmd.LIST_PEERS:
            peers = [
                {
                    "id": "buster",
                    "status": "simulated"
                }
            ]

            self._send_binary(
                Rsp.PEER_LIST,
                json.dumps(peers).encode()
            )

    def _reader(self) -> None:
        while self.running:
            try:
                chunk = self.ser.read(4096)

                if not chunk:
                    continue

                print(
                    f"[SAKA] Rohdaten empfangen: {chunk!r}",
                    flush=True
                )

                # Zuerst einfache Textbefehle prüfen.
                if self._handle_text_command(chunk):
                    continue

                # Falls es kein Textbefehl war:
                # als binären Protokollframe verarbeiten.
                self.buf += chunk

                frames, self.buf = parse_frames(self.buf)

                for cmd_type, payload in frames:
                    self._handle_binary_command(
                        cmd_type,
                        payload
                    )

            except serial.SerialException as exc:
                print(
                    f"[SAKA] Serial-Fehler: {exc}",
                    flush=True
                )
                time.sleep(1)

            except Exception as exc:
                print(
                    f"[SAKA] Fehler: {exc}",
                    flush=True
                )
                time.sleep(0.2)

    def run(self) -> None:
        reader_thread = threading.Thread(
            target=self._reader,
            daemon=True
        )

        reader_thread.start()

        try:
            while self.running:
                time.sleep(1)

        except KeyboardInterrupt:
            print(
                "[SAKA] Stop durch Benutzer",
                flush=True
            )

        finally:
            self.running = False
            self.ser.close()

            print(
                "[SAKA] Server beendet",
                flush=True
            )


if __name__ == "__main__":
    SakaServer().run()

