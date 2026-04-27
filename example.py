# -*- coding: utf-8 -*-
"""
@File    : example.py
@Author  : Roney D. Silva e Equipe EFO-S (refatorado)
@Desc    : Script de teste organizado para RotTableWrapper
"""

from rotatorytable import RotTableWrapper
from time import sleep

# =========================================================
# CONFIG
# =========================================================

SERVER_TEST = "192.168.1.1"
MODBUS_PORT_TEST = 502

SLEEP_MOVE = 5
SLEEP_SHORT = 2

# =========================================================
# HELPERS
# =========================================================

def wait(t=SLEEP_MOVE):
    sleep(t)

def print_title(msg):
    print("\n" + "=" * 60)
    print(msg)
    print("=" * 60)

def print_axis_state(rot):
    pos_yaw = rot.get_pos_yaw()
    pos_roll = rot.get_pos_roll()
    vel_yaw = rot.get_vel_yaw()
    vel_roll = rot.get_vel_roll()

    print(f"YAW  → pos={pos_yaw:.4f}° | vel={vel_yaw:.4f}°/s")
    print(f"ROLL → pos={pos_roll:.4f}° | vel={vel_roll:.4f}°/s\n")

# =========================================================
# TESTES
# =========================================================

def test_move(rot):
    print_title("TESTE: POSICIONAMENTO (MOVE)")

    print("→ YAW = 45°")
    rot.move_yaw(45)
    wait()
    print_axis_state(rot)
    wait

    print("→ ROLL = 30°")
    rot.move_roll(30)
    wait()
    print_axis_state(rot)
    wait(SLEEP_SHORT)

    print("→ YAW & ROLL = 0°")
    rot.move_all(0)
    wait()
    print_axis_state(rot)
    wait(SLEEP_SHORT)


def test_jog(rot):
    print_title("TESTE: JOG (VELOCIDADE CONTÍNUA)")

    print("→ YAW +20°/s")
    rot.jog_yaw(20)
    wait()
    print_axis_state(rot)
    wait(SLEEP_SHORT)

    print("→ STOP YAW")
    rot.stop_yaw()
    wait()
    print_axis_state(rot)
    wait(SLEEP_SHORT)

    print("→ ROLL -15°/s")
    rot.jog_roll(-15)
    wait()
    print_axis_state(rot)
    wait(SLEEP_SHORT)

    print("→ STOP ROLL")
    rot.stop_roll()
    wait()
    print_axis_state(rot)
    wait(SLEEP_SHORT)

    print("→ YAW -30°/s")
    rot.jog_yaw(-30)
    wait()
    print_axis_state(rot)
    wait(SLEEP_SHORT)

    print("→ STOP YAW")
    rot.stop_yaw()
    wait()


def test_jog_all(rot):
    print_title("TESTE: JOG COMBINADO")

    print("→ YAW & ROLL = +10°/s")
    rot.jog_all(10)
    wait()
    print_axis_state(rot)
    wait(SLEEP_SHORT)

    print("→ STOP ALL")
    rot.stop_all()
    wait()
    print_axis_state(rot)
    wait(SLEEP_SHORT)

    print("→ YAW & ROLL = +90°/s")
    rot.jog_all(90)
    wait()
    print_axis_state(rot)
    wait(SLEEP_SHORT)

    print("→ STOP ALL")
    rot.stop_all()
    wait()
    print_axis_state(rot)
    wait(SLEEP_SHORT)

def test_homing(rot):
    print_title("TESTE: HOMING MANUAL")

    print("→ Retorno para 0°")
    rot.move_all(0)
    wait(7)
    print_axis_state(rot)
    wait(SLEEP_SHORT)

def test_emergency(rot):
    print_title("TESTE: EMERGÊNCIA")

    print("→ Jog ALL 20°/s")
    rot.jog_all(20)
    wait()

    print("→ EMERGENCY STOP")
    rot.emergency_stop()
    wait()
    print_axis_state(rot)
    wait(SLEEP_SHORT)
    print("RESET executado")
    wait(SLEEP_MOVE)
        

    print("→ EMERGENCY_RESET")
    rot.emergency_reset()
    wait()

    print("→ Teste pós-reset (jog all 10°/s)")
    rot.jog_all(10)
    wait()
    print_axis_state(rot)
    wait()

    print("→ STOP ALL")
    rot.stop_all()
    wait()
    print_axis_state(rot)
    wait(SLEEP_SHORT)

    print("→ HOMING FINAL")
    rot.move_all(0)
    wait(8)
    print_axis_state(rot)
    wait(SLEEP_SHORT)



# =========================================================
# MAIN
# =========================================================

def main():
    print_title("INICIANDO TESTES DA MESA INERCIAL")

    rot = RotTableWrapper(
        host=SERVER_TEST,
        port=MODBUS_PORT_TEST
    )

    test_move(rot)
    test_jog(rot)
    test_jog_all(rot)
    test_homing(rot)
    test_emergency(rot)

    print_title("TESTE FINALIZADO")


if __name__ == "__main__":
    main()