import struct

MAGIC = b'USRS'
VERSION = 0x01
HEADER_SIZE = 10


class Cmd:
    PING = 0x01
    STATUS = 0x02
    SEND_MSG = 0x03
    CONNECT = 0x04
    DISCONNECT = 0x05
    LIST_PEERS = 0x06


class Rsp:
    PONG = 0x11
    STATUS_OK = 0x12
    MSG_SENT = 0x13
    CONNECT_OK = 0x14
    CONNECT_ERR = 0x15
    MSG_RECV = 0x16
    PEER_LIST = 0x17
    REJECT = 0xFF


ALLOWED_CMDS = {
    Cmd.PING,
    Cmd.STATUS,
    Cmd.SEND_MSG,
    Cmd.CONNECT,
    Cmd.DISCONNECT,
    Cmd.LIST_PEERS,
}


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc = crc >> 1
    return crc & 0xFFFF


def build_frame(frame_type: int, payload: bytes = b'') -> bytes:
    header = MAGIC + bytes([VERSION, frame_type]) + struct.pack('>I', len(payload))
    body = header + payload
    return body + struct.pack('>H', crc16(body))


def parse_frames(buffer: bytes):
    frames = []

    while True:
        idx = buffer.find(MAGIC)

        if idx == -1:
            buffer = b''
            break

        if idx > 0:
            buffer = buffer[idx:]

        if len(buffer) < HEADER_SIZE + 2:
            break

        version = buffer[4]
        frame_type = buffer[5]
        length = struct.unpack('>I', buffer[6:10])[0]

        if version != VERSION:
            buffer = buffer[1:]
            continue

        if length > 65536:
            buffer = buffer[1:]
            continue

        total = HEADER_SIZE + length + 2

        if len(buffer) < total:
            break

        frame = buffer[:total]
        received_crc = struct.unpack('>H', frame[-2:])[0]
        calculated_crc = crc16(frame[:-2])

        if received_crc != calculated_crc:
            buffer = buffer[1:]
            continue

        payload = frame[HEADER_SIZE:-2]
        frames.append((frame_type, payload))
        buffer = buffer[total:]

    return frames, buffer
