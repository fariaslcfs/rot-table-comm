# -*- coding: utf-8 -*-
"""
@File    : example.py
@Time    : 2024/03/22 00:12:15
@Author  : Roney D. Silva e Equipe EFO-S

Descrição:
    Exemplo de uso da classe RotTableComm para controle da mesa inercial
    com dois eixos (Azimuth e Tilt) via Modbus TCP.

Compatibilidade:
    Python 3.12.3, pymodbus 3.7.4
"""

from rotatorytable import RotTableWrapper
from time import sleep

# =========================================================
# CONFIGURAÇÃO DE AMBIENTE
# =========================================================

SERVER_PROD = "192.168.1.1"      # Mesa real
MODBUS_PORT_PROD = 502                # Porta padrão Modbus TCP

SERVER_TEST = "127.0.0.1"        # Simulador local. Lembre-se de iniciar o simulador antes de executar este script.
MODBUS_PORT_TEST = 5020          # Evita conflito com porta 502 (well-known)

# =========================================================
# OBSERVAÇÃO IMPORTANTE (SIMULADOR)
# =========================================================
"""
Para execução do simulador sem interação manual, é necessário o arquivo:
    mesa_config.json

Este arquivo é o mesmo utilizado pelo projeto ScriptMesaPython:
    https://github.com/IEAv-EFO/ScriptMesaPython.git
"""

# =========================================================
# INSTANCIAÇÃO DO CONTROLADOR
# =========================================================

rot = RotTableWrapper(host=SERVER_PROD, port=MODBUS_PORT_PROD)

# =========================================================
# 1. HABILITAR SISTEMA
# =========================================================

print("Conectando..")
rot.connect()
sleep(1) # Aguarda o sistema ser habilitado

# =========================================================
# 2. TESTE DE MOVE - POSICIONAMENTO ABSOLUTO
# =========================================================

'''
SOBRE OS SLEEPS: 
Eles são necessários para garantir que o sistema tenha tempo suficiente
para processar os comandos e alcançar as posições desejadas antes de enviar o próximo comando. 
Sem esses delays, os comandos podem ser enviados em rápida sucessão, o que pode causar comportamento
inesperado ou falhas no controle da mesa inercial.

# TODO: Seria ideal implementar uma função de espera baseada no status do movimento, observando o valor dos 
registradores de trigger, em vez de usar sleep fixo.
Exemplo: aguardar até que o movimento seja concluído verificando o status do eixo.
Enquanto isso, o sleep é utilizado aqui para simplificar. Então, deve-se, com base na velocidade de posicionamento, 
ajustar o tempo de espera para garantir que o movimento seja concluído antes de enviar o próximo comando.

'''

print("TESTE DE POSICIONAMENTO DOS EIXOS YAW e ROLL\n")

print("Move o eixo yaw para 45 graus")
rot.move_yaw(45)
sleep(5)
pos = rot.get_pos_yaw()
print(f"Posição atual do eixo YAW: {pos:.4f} graus\n")
sleep(2) 

print("Move o eixo roll para 30 graus")
rot.move_roll(30)
sleep(5)
pos = rot.get_pos_roll()
print(f"Posição atual do eixo ROLL: {pos:.4f} graus\n")
sleep(2)

print("Move os eixos yaw e roll para 0 graus")
rot.move_yaw(0)
rot.move_roll(0)
sleep(5)
pos_yaw = rot.get_pos_yaw()
pos_roll = rot.get_pos_roll()
print(f"Posição atual do eixo YAW: {pos_yaw:.4f} graus")
print(f"Posição atual do eixo ROLL: {pos_roll:.4f} graus\n")
sleep(2)

# =========================================================
# 3. TESTE DE JOG  - VELOCIDADE CONTÍNUA
# =========================================================

print("Jog yaw com velocidade 20 °/s")
rot.jog_yaw(20)
sleep(5)
vel = rot.get_vel_yaw()
print(f"Velocidade atual do eixo YAW: {vel:.4f} °/s\n")
sleep(2)

print("Para o jog yaw")
rot.stop_yaw()
sleep(5)
vel = rot.get_vel_yaw()
print(f"Velocidade atual do eixo YAW após stop: {vel:.4f} °/s\n")
sleep(2) 

print("Jog roll com velocidade 15 °/s no sentido negativo")
rot.jog_roll(-15)
sleep(5)
vel = rot.get_vel_roll()
print(f"Velocidade atual do eixo ROLL: {vel:.4f} °/s\n")
sleep(2)

print("Para o jog Roll")
rot.stop_roll()
sleep(5)
vel = rot.get_vel_roll()
print(f"Velocidade atual do eixo ROLL após stop: {vel:.4f} °/s\n")
sleep(2)

print("Jog yaw com velocidade 30 °/s no sentido negativo")
rot.jog_yaw(-30)
sleep(5)
vel = rot.get_vel_yaw()
print(f"Velocidade atual do eixo YAW: {vel:.4f} °/s\n")
sleep(2)

print("Para o jog yaw")
rot.jog_roll(0)
sleep(2)

print("Jog roll com velocidade 20 °/s")
rot.jog_roll(20)
sleep(5)
vel = rot.get_vel_roll()
print(f"Velocidade atual do eixo ROLL: {vel:.4f} °/s\n")
sleep(5)

print("Para os jogs yaw e roll")
rot.stop_all()
sleep(5)
vel_yaw = rot.get_vel_yaw()
vel_roll = rot.get_vel_roll()
print(f"Velocidade atual do eixo YAW após stop: {vel_yaw:.4f} °/s")
print(f"Velocidade atual do eixo ROLL após stop: {vel_roll:.4f} °/s\n")
sleep(5)

# =========================================================
# 4. TESTE DE MÉTODOS DE MOVIMENTO COMBINADO (DOIS EIXOS)
# =========================================================

print("Jog nos eixos yaw e roll com velocidade de 10 °/s")
rot.jog_all(10)
sleep(5)
vel_yaw = rot.get_vel_yaw()
vel_roll = rot.get_vel_roll()
print(f"Velocidade atual do eixo YAW: {vel_yaw:.4f} °/s")
print(f"Velocidade atual do eixo ROLL: {vel_roll:.4f} °/s\n")
sleep(2)   

print("Para os eixos yaw e roll")
rot.stop_all()
sleep(5)
vel_yaw = rot.get_vel_yaw()
vel_roll = rot.get_vel_roll()
print(f"Velocidade atual do eixo YAW após stop: {vel_yaw:.4f} °/s")
print(f"Velocidade atual do eixo ROLL após stop: {vel_roll:.4f} °/s\n")
sleep(2)   

print("Jog nos eixos yaw e roll com velocidade de 90 °/s")
rot.jog_all(90.0)
sleep(5)
vel_all = rot.get_vel_all()
print(f"Velocidade atual do eixo YAW: {vel_all[0]:.4f} °/s")
print(f"Velocidade atual do eixo ROLL: {vel_all[1]:.4f} °/s\n")
sleep(2)    

print("Para os eixos yaw e roll")
rot.stop_all()
sleep(5)
vel_yaw = rot.get_vel_yaw()
vel_roll = rot.get_vel_roll()
print(f"Velocidade atual do eixo YAW após stop: {vel_yaw:.4f} °/s")
print(f"Velocidade atual do eixo ROLL após stop: {vel_roll:.4f} °/s\n")
sleep(2)

# ==============================================================
# 5. HOMING MANUAL - retorno "para casa" ao zero mecânico lógico 
# ==============================================================

print("Retorno ao zero mecânico lógico (homing manual)")
print("Move os eixos yaw e roll para 0 graus")
rot.move_all(0)
sleep(5)
pos_yaw = rot.get_pos_yaw()
pos_roll = rot.get_pos_roll()
print(f"Posição atual do eixo YAW: {pos_yaw:.4f} graus")
print(f"Posição atual do eixo ROLL: {pos_roll:.4f} graus\n")
sleep(2)

print("Teste finalizado com sucesso.")