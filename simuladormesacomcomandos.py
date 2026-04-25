# VERSÃO FINAL ESTÁVEL COM EMERGENCY CORRETO (COMPORTAMENTO REAL)

import time
import threading
import json
import os

from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusServerContext, ModbusSlaveContext, ModbusSequentialDataBlock
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ==============================
# CONFIG
# ==============================
SERVER = "127.0.0.1"
MODBUS_PORT = 5020
CONFIG_FILE = "mesa_config.json"

config_lock = threading.Lock()
emergency_active = False

# ==============================
# VARIÁVEIS DINÂMICAS
# ==============================

pos_ini_azi = 0.0
pos_ini_tilt = 0.0

vel_ini_azi = 0.0
vel_ini_tilt = 0.0

acc_azi = 100.0
acc_tilt = 100.0

cruise_vel_azi = 30.0
cruise_vel_tilt = 30.0

K = 1.0
DT = 0.001

# ==============================
# INPUT
# ==============================

def input_float(msg, default):
    val = input(f"{msg} [{default}]: ").strip()
    return float(val) if val else default

def escolher_modo():
    while True:
        modo = input("Modo [I]nterativo / [J]SON? (I/J): ").strip().lower()
        if modo in ("i", "j"):
            return modo
        print("Opção inválida.")

# ==============================
# CONFIG
# ==============================

def load_config_file():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("Erro ao ler config:", e)
        return {}

def apply_config(cfg):
    global pos_ini_azi, pos_ini_tilt
    global vel_ini_azi, vel_ini_tilt
    global acc_azi, acc_tilt
    global cruise_vel_azi, cruise_vel_tilt
    global K, DT

    pos_ini_azi = float(cfg.get("posIniAzimute", pos_ini_azi))
    pos_ini_tilt = float(cfg.get("posIniTilt", pos_ini_tilt))

    vel_ini_azi = float(cfg.get("velIniAzimute", vel_ini_azi))
    vel_ini_tilt = float(cfg.get("velIniTilt", vel_ini_tilt))

    acc_azi = float(cfg.get("accPosAzimute", acc_azi))
    acc_tilt = float(cfg.get("accPosTilt", acc_tilt))

    cruise_vel_azi = float(cfg.get("velPosAzimute", cruise_vel_azi))
    cruise_vel_tilt = float(cfg.get("velPosTilt", cruise_vel_tilt))

    K = float(cfg.get("K", K))
    DT = float(cfg.get("DT", DT))

    print("\n🔄 CONFIG ATUALIZADA EM RUNTIME")
    print(f"AZI  pos={pos_ini_azi} vel={vel_ini_azi} acc={acc_azi} cruise={cruise_vel_azi}")
    print(f"TILT pos={pos_ini_tilt} vel={vel_ini_tilt} acc={acc_tilt} cruise={cruise_vel_tilt}\n")

# ==============================
# WATCHDOG
# ==============================

class ConfigWatcher(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(CONFIG_FILE):
            time.sleep(0.2)
            with config_lock:
                cfg = load_config_file()
                apply_config(cfg)

def start_watcher():
    observer = Observer()
    observer.schedule(ConfigWatcher(), path=".", recursive=False)
    observer.start()
    return observer

# ==============================
# MODO INICIAL
# ==============================

modo = escolher_modo()

if modo == "i":
    print("\n=== CONFIGURAÇÃO INTERATIVA ===")

    pos_ini_azi = input_float("Posição inicial AZI", 0.0)
    pos_ini_tilt = input_float("Posição inicial TILT", 0.0)

    vel_ini_azi = input_float("Velocidade inicial AZI", 0.0)
    vel_ini_tilt = input_float("Velocidade inicial TILT", 0.0)

    acc_azi = input_float("Aceleração AZI", 100.0)
    acc_tilt = input_float("Aceleração TILT", 100.0)

    cruise_vel_azi = input_float("Velocidade cruzeiro AZI", 30.0)
    cruise_vel_tilt = input_float("Velocidade cruzeiro TILT", 30.0)

    K = input_float("K", 1.0)
    DT = input_float("DT", 0.001)

else:
    print("\n=== CONFIGURAÇÃO JSON ===")
    cfg = load_config_file()
    apply_config(cfg)

# ==============================
# MODBUS STORE
# ==============================

store = ModbusSlaveContext(
    ir=ModbusSequentialDataBlock(0, [0]*200),
    hr=ModbusSequentialDataBlock(0, [0]*200)
)
context = ModbusServerContext(slaves=store, single=True)

# ==============================
# AXIS
# ==============================

class Axis:
    def __init__(self, max_vel):
        self.pos = 0.0
        self.vel = 0.0
        self.max_vel = max_vel

azi = Axis(500.0)
tilt = Axis(200.0)

azi.pos = pos_ini_azi
azi.vel = vel_ini_azi
tilt.pos = pos_ini_tilt
tilt.vel = vel_ini_tilt

lock = threading.Lock()

# ==============================
# HELPERS
# ==============================

def write_ir(addr, value):
    low = value & 0xFFFF
    high = (value >> 16) & 0xFFFF
    context[0].setValues(4, addr, [low, high])

def write_ir_signed(addr, value):
    if value < 0:
        value = (1 << 32) + value
    write_ir(addr, value)

def read_hr(addr):
    return context[0].getValues(3, addr, count=1)[0]

def read_dword(addr):
    vals = context[0].getValues(3, addr, count=2)
    return (vals[1] << 16) | vals[0]

# ==============================
# EMERGENCY HANDLER
# ==============================

def handle_emergency():
    global emergency_active

    cmd = read_hr(20)

    if cmd == 4:
        emergency_active = True
        context[0].setValues(3, 20, [0])  # ACK

        # Zera dinâmica
        azi.vel = 0
        tilt.vel = 0

        # Limpa comandos
        context[0].setValues(3, 26, [0])
        context[0].setValues(3, 28, [0])
        context[0].setValues(3, 46, [0, 0])
        context[0].setValues(3, 56, [0, 0])

    elif cmd == 1:
        emergency_active = False
        context[0].setValues(3, 20, [0])  # ACK

        # Limpa comandos novamente (evita retorno)
        context[0].setValues(3, 26, [0])
        context[0].setValues(3, 28, [0])

# ==============================
# DINÂMICA
# ==============================

def angular_error(target, current):
    return (target - current + 180) % 360 - 180

def update_axis(axis, vel_cmd, target, mode, acc, cruise_vel):
    if mode == "position":
        error = angular_error(target, axis.pos)
        direction = 1 if error > 0 else -1 if error < 0 else 0

        stop_dist = (axis.vel ** 2) / (2 * acc) if acc > 0 else 0

        if abs(error) <= stop_dist:
            axis.vel -= acc * DT if axis.vel > 0 else -acc * DT
        else:
            desired_vel = direction * cruise_vel

            if axis.vel < desired_vel:
                axis.vel += acc * DT
            elif axis.vel > desired_vel:
                axis.vel -= acc * DT

    elif mode == "velocity":
        if axis.vel < vel_cmd:
            axis.vel += acc * DT
        elif axis.vel > vel_cmd:
            axis.vel -= acc * DT

    else:
        axis.vel *= 0.98

    if abs(axis.vel) > axis.max_vel:
        axis.vel = axis.max_vel if axis.vel > 0 else -axis.max_vel

    axis.pos += axis.vel * DT
    axis.pos %= 360

# ==============================
# LOOP
# ==============================

def loop():
    while True:
        time.sleep(K * DT)

        with lock:
            handle_emergency()

            if emergency_active:
                # trava total
                azi.vel = 0
                tilt.vel = 0

                write_ir_signed(2, 0)
                write_ir_signed(6, 0)

                write_ir(0, int(azi.pos * 1_000_000))
                write_ir(4, int(tilt.pos * 1_000_000))
                continue

            cmd_tilt = read_hr(26)
            cmd_azi = read_hr(28)

            vel_tilt_cmd = read_dword(46) / 100.0
            vel_azi_cmd = read_dword(56) / 100.0

            target_tilt = read_dword(60) / 1000.0
            target_azi = read_dword(70) / 1000.0

            mode_tilt = "idle"
            mode_azi = "idle"

            if cmd_tilt == 4:
                mode_tilt = "position"
            elif cmd_tilt in (1, 2):
                mode_tilt = "velocity"
                vel_tilt_cmd = vel_tilt_cmd if cmd_tilt == 1 else -vel_tilt_cmd

            if cmd_azi == 4:
                mode_azi = "position"
            elif cmd_azi in (1, 2):
                mode_azi = "velocity"
                vel_azi_cmd = vel_azi_cmd if cmd_azi == 1 else -vel_azi_cmd

            update_axis(tilt, vel_tilt_cmd, target_tilt, mode_tilt, acc_tilt, cruise_vel_tilt)
            update_axis(azi, vel_azi_cmd, target_azi, mode_azi, acc_azi, cruise_vel_azi)

            write_ir(0, int(azi.pos * 1_000_000))
            write_ir_signed(2, int(azi.vel * 1_000_000))
            write_ir(4, int(tilt.pos * 1_000_000))
            write_ir_signed(6, int(tilt.vel * 1_000_000))

# ==============================
# MAIN
# ==============================

if __name__ == "__main__":
    print(f"Simulador rodando em {SERVER}:{MODBUS_PORT}\n")

    observer = start_watcher()
    threading.Thread(target=loop, daemon=True).start()

    try:
        StartTcpServer(context=context, address=(SERVER, MODBUS_PORT))
    finally:
        observer.stop()
        observer.join()