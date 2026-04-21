# RotTableWrapper (RotTableComm refatorada) — Classe de Controle da Mesa Inercial (Python 3.12+)

Autor: Roney D. Silva e equipe EFO-S  

---

## 1. Visão Geral

A classe `RotTableWrapper` fornece uma interface de alto nível para controle de uma mesa inercial de dois eixos (**Azimuth** e **Tilt**) via protocolo **Modbus TCP**.

Ela encapsula:

- Controle de posição absoluta
- Controle de velocidade (jog)
- Configuração de ganhos e limites
- Conversão de valores 32 bits (INT32 via dois registradores 16 bits)
- Normalização de ângulos
- Sequência correta de comandos do controlador da mesa
- Delays obrigatórios (`time.sleep`) para sincronização com o firmware

---

## 2. Dependências

~~~
pip install -r requirements.txt
~~~

---

## 3. Conceitos Importantes

### 3.1 Registradores INT32 (2x16 bits)

O controlador da mesa utiliza registradores de 16 bits.  
Valores maiores (posição/velocidade) são armazenados em 32 bits:

~~~
valor_32bits = HIGH << 16 | LOW
~~~

---

### 3.2 Escalas

| Parâmetro  | Escala |
|------------|--------|
| Posição    | ×1000  |
| Velocidade | ×100   |

---

### 3.3 Normalização de Ângulo

Todos os ângulos são convertidos para o intervalo:

~~~
[0, 360000)
~~~

Função:

~~~
normalize(angle):
    angle = angle * 1000
    if angle < 0:
        angle = 360000 - abs(angle)
    return angle
~~~

---

## 4. Registradores do Controlador da Mesa

### Input Registers (Leitura)

| Addr | Eixo   | Descrição |
|------|--------|----------|
| 0-1  | Azimuth | Posição |
| 2-3  | Azimuth | Velocidade |
| 4-5  | Tilt    | Posição |
| 6-7  | Tilt    | Velocidade |

---

### Holding Registers (Controle)

| Addr | Função | Observação |             
|------|--------|------------|
| 22   | Enable Tilt |
| 24   | Enable Azimuth |
| 26   | CMD Tilt |
| 28   | CMD Azimuth |
| 40   | Acc Tilt |
| 42   | Max Acc Tilt |
| 50   | Acc Azimuth |
| 52   | Max Acc Azimuth |
| 46-47| Vel Tilt |         * O valor máximo de velocidade não ultrapassa 65535 (16 bits) usando somente 1 registrador |
| 56-57| Vel Azimuth |      * O valor máximo de velocidade não ultrapassa 65535 (16 bits) usando somente 1 registrador |
| 60-61| Target Tilt |      * Para o valor do target (posição angular de azimute), 2 registradores de 16 bits são usados | 
| 70-71| Target Azimuth |   * Para o valor do target (posição angular de inclinação), 2 registradores de 16 bits são usados | 
| 80   | MaxVelTitl |       * Tilt max velocity |
| 82   | MaxAccTilt |       * Tilt max acceleration |
| 90   | MaxVelAzi |        * Azimuth max velocity |
| 92   | MaxAccAzi |        * Azimuth max acceleration |
---

## 5. Classe Refatorada

~~~
from pymodbus.client import ModbusTcpClient
import time

SERVER_PROD = "192.168.1.1"    # Mesa real Infax
MODBUS_PORT = 502              # Porta padrão Modbus TCP  
SERVER_TEST = "127.0.0.1"      # Simulador local. Lembre-se de iniciar o simulador antes de executar este script.
MODBUS_PORT_TEST = 5020        # Evita conflito com porta 502 (well-known)

class RotTableWrapper:
    
    """
    Wrapper para controle da mesa inercial Infax da EFO-S
    via Modbus TCP (pymodbus 3.x+ / 4.x compatível). 
    Objetivo: simplicidade de uso em laboratório.
    
    """

    def __init__(self, host=SERVER_TEST, port=MODBUS_PORT_TEST):
        self.host = host
        self.port = port
        self.client = ModbusTcpClient(host=host, port=port)

        # limites básicos (engenharia)
        self.max_vel = 50000
        self.max_acc = 10000

    # =====================================================
    # CONEXÃO
    # =====================================================

    def connect(self):
        return self.client.connect()

    def close(self):
        self.client.close()

    def _ensure_connection(self):
        if not self.client.connected:
            self.client.connect()

    # =====================================================
    # NÚCLEO MODBUS ou HELPERS
    # =====================================================

    def write(self, addr, value):
        self._ensure_connection()
        return self.client.write_register(address=addr, value=int(value))

    def write_dword(self, addr, value):
        """Escreve 32 bits em dois registradores 16 bits"""
        value = int(value)
        low = value & 0xFFFF
        high = (value >> 16) & 0xFFFF

        self.write(addr, low)
        self.write(addr + 1, high)

    def read_input(self, addr, count=2):
        self._ensure_connection()
        return self.client.read_input_registers(address=addr, count=count)

    def normalize(self, angle_deg: float) -> int:
        """
        Converte graus → formato controlador (×1000)
        e normaliza 0–360°
        """
        v = int(angle_deg * 1000)
        if v < 0:
            v = 360000 - abs(v)
        return v

    # =====================================================
    # ENABLE / STOP
    # =====================================================

    def enable(self):
        self.write(22, 1)
        self.write(24, 1)

    def disable(self):
        self.write(22, 0)
        self.write(24, 0)

    def stop(self):
        self.write(26, 0)
        self.write(28, 0)

    # =====================================================
    # VELOCIDADE (JOG)
    # =====================================================

    def jogazi(self, value: float):

        self.write(50, 10000)
        self.write(52, 10000)
        self.write(24, 1)
        self.write(22, 1)

        v = value * 100.0

        if v > self.max_vel:
            v = self.max_vel
        if v < -self.max_vel:
            v = -self.max_vel

        if v < 0:
            self.write_dword(56, abs(int(v)))
            self.write(28, 2)
        elif v > 0:
            self.write_dword(56, int(v))
            self.write(28, 1)
        else:
            self.write(28, 0)

    def jogtilt(self, value: float):

        self.write(22, 2)
        time.sleep(0.02)

        self.write(26, 0)
        time.sleep(0.02)

        self.write(40, 10000)
        self.write(42, 10000)

        v = value * 100.0

        if v > self.max_vel:
            v = self.max_vel
        if v < -self.max_vel:
            v = -self.max_vel

        if v < 0:
            self.write_dword(46, abs(int(v)))
            self.write(26, 2)
        elif v > 0:
            self.write_dword(46, int(v))
            self.write(26, 1)
        else:
            self.write(26, 0)

        time.sleep(0.02)

    def jog(self, velocity: float):
        self.jogazi(velocity)
        self.jogtilt(velocity)

    # =====================================================
    # POSIÇÃO
    # =====================================================

    def posazi(self, angle: float):

        pos = self.normalize(angle)

        self.write(24, 2)
        time.sleep(0.02)

        self.write(28, 0)
        time.sleep(0.02)

        self.write_dword(70, pos)

        self.write(50, 10000)
        self.write(52, 10000)

        time.sleep(0.02)

        self.write(28, 4)

    def postilt(self, angle: float):

        pos = self.normalize(angle)

        self.write(22, 2)
        time.sleep(0.02)

        self.write(26, 0)
        time.sleep(0.02)

        self.write_dword(60, pos)

        self.write(40, 10000)
        self.write(42, 10000)

        time.sleep(0.02)

        self.write(26, 4)

    def pos(self, angle: float):
        self.posazi(angle)
        self.postilt(angle)

    # =====================================================
    # LEITURA (FEEDBACK)
    # =====================================================

    def getposazi(self):
        r = self.read_input(0, 2)
        if r.isError():
            return None
        return ((r.registers[1] << 16) + r.registers[0]) / 1_000_000

    def getpostilt(self):
        r = self.read_input(4, 2)
        if r.isError():
            return None
        return ((r.registers[1] << 16) + r.registers[0]) / 1_000_000
    
    def getpos(self):
        return self.getposazi(), self.getpostilt()
    
    def getvelazi(self):
        r = self.read_input(8, 2)
        if r.isError():
            return None
        return ((r.registers[1] << 16) + r.registers[0]) / 100.0

    def getveltilt(self):
        r = self.read_input(12, 2)
        if r.isError():
            return None
        return ((r.registers[1] << 16) + r.registers[0]) / 100.0
    
    def getvel(self):
        return self.getvelazi(), self.getveltilt()

    
~~~

---

## 7. Observações de Engenharia

- `time.sleep(0.02)` é obrigatório para sincronização do controlador da mesa
- Registradores devem ser escritos na ordem correta:
  1. Enable
  2. Reset comando
  3. Escrita de posição/velocidade
  4. Start comando
- Azimuth e Tilt são independentes, mas compartilham o mesmo barramento lógico
- Falha em sequência pode gerar comportamento indeterminado no movimento

---

## 8. Ponto Crítico

O controlador da mesa NÃO aceita diretamente valores fora da escala:

- Posicionamento: sempre ×1000
- Velocidade: sempre ×100
- INT32 deve ser sempre dividido em LOW/HIGH

---

## 9. Extensões Futuras

- Retry automático Modbus
- Execução de scripts de movimento

# 👥 Equipe
**Roney e EFO-S**