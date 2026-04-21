# RotTableComm — Classe de Controle da Mesa Inercial (Python 3.12+)

Autor: Roney D. Silva e equipe EFO-S  

---

## 1. Visão Geral

A classe `RotTableComm` fornece uma interface de alto nível para controle de uma mesa inercial de dois eixos (**Azimuth** e **Tilt**) via protocolo **Modbus TCP**.

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
pip install pyModbusTCP
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

| Addr | Função |
|------|--------|
| 22   | Enable Tilt |
| 24   | Enable Azimuth |
| 26   | CMD Tilt |
| 28   | CMD Azimuth |
| 40   | Acc Tilt |
| 42   | Max Acc Tilt |
| 50   | Acc Azimuth |
| 52   | Max Acc Azimuth |
| 46-47| Vel Tilt |
| 56-57| Vel Azimuth |
| 60-61| Target Tilt |
| 70-71| Target Azimuth |

---

## 5. Classe Refatorada

~~~
import time
from pyModbusTCP.client import ModbusClient


class RotTableComm:
    """
    Interface de controle da mesa inercial (Azimuth + Tilt)
    via Modbus TCP.
    """

    def __init__(self, host="192.168.1.1", port=502):

        self.client = ModbusClient(host=host, port=port)
        self.max_acc = 10000
        self.max_vel = 50000

        if not self.client.open():
            raise ConnectionError("Falha ao conectar no controlador da mesa")

        self.client.close()

    # =========================
    # UTIL
    # =========================

    def _write(self, addr, value):
        if not self.client.is_open:
            self.client.open()
        self.client.write_single_register(addr, value)
        self.client.close()

    def _write_dword(self, addr, value):
        low = value & 0xFFFF
        high = (value >> 16) & 0xFFFF
        self._write(addr, low)
        self._write(addr + 1, high)

    def normalize(self, angle_deg: float) -> int:
        """
        Converte graus para formato do controlador da mesa (×1000)
        e normaliza para [0..360000)
        """
        v = int(angle_deg * 1000)
        if v < 0:
            v = 360000 - abs(v)
        return v

    # =========================
    # ENABLE
    # =========================

    def enable(self):
        self._write(22, 1)
        self._write(24, 1)

    def disable(self):
        self._write(22, 0)
        self._write(24, 0)

    # =========================
    # STOP
    # =========================

    def stop(self):
        self._write(26, 0)
        self._write(28, 0)

    # =========================
    # VELOCIDADE AZIMUTH
    # =========================

    def set_azimuth_velocity(self, value: float):

        self._write(50, 10000)
        self._write(52, 10000)
        self._write(24, 1)
        self._write(22, 1)

        v = value * 100.0

        if v < 0:
            self._write_dword(56, int(abs(v)))
            self._write(28, 2)
        elif v > 0:
            self._write_dword(56, int(v))
            self._write(28, 1)
        else:
            self._write(28, 0)

    # =========================
    # VELOCIDADE TILT
    # =========================

    def set_tilt_velocity(self, value: float):

        self._write(22, 2)
        time.sleep(0.02)

        self._write(26, 0)
        time.sleep(0.02)

        self._write_dword(60, 0)  # reservado para compatibilidade

        self._write(40, 10000)
        self._write(42, 10000)

        v = value * 100.0

        if v < 0:
            self._write_dword(46, int(abs(v)))
            self._write(26, 2)
        elif v > 0:
            self._write_dword(46, int(v))
            self._write(26, 1)
        else:
            self._write(26, 0)

        time.sleep(0.02)

    # =========================
    # POSIÇÃO AZIMUTH
    # =========================

    def set_azimuth_position(self, angle_deg: float):

        pos = self.normalize(angle_deg)

        self._write(24, 2)
        time.sleep(0.02)

        self._write(28, 0)
        time.sleep(0.02)

        self._write_dword(70, pos)

        self._write(50, 10000)
        self._write(52, 10000)

        time.sleep(0.02)

        self._write(28, 4)

    # =========================
    # POSIÇÃO TILT
    # =========================

    def set_tilt_position(self, angle_deg: float):

        pos = self.normalize(angle_deg)

        self._write(22, 2)
        time.sleep(0.02)

        self._write(26, 0)
        time.sleep(0.02)

        self._write_dword(60, pos)

        self._write(40, 10000)
        self._write(42, 10000)

        time.sleep(0.02)

        self._write(26, 4)

    # =========================
    # JOG
    # =========================

    def jog(self, axis: str, velocity: float):

        if axis == "azimuth":
            self.set_azimuth_velocity(velocity)

        elif axis == "tilt":
            self.set_tilt_velocity(velocity)

        elif axis == "both":
            self.set_azimuth_velocity(velocity)
            self.set_tilt_velocity(velocity)

    # =========================
    # POSIÇÃO GENÉRICA
    # =========================

    def pos(self, axis: str, angle: float):

        if axis == "azimuth":
            self.set_azimuth_position(angle)

        elif axis == "tilt":
            self.set_tilt_position(angle)

        elif axis == "both":
            self.set_azimuth_position(angle)
            self.set_tilt_position(angle)
~~~

---

## 6. Exemplo de Uso

~~~
from rot_table_comm import RotTableComm

rt = RotTableComm()

rt.enable()

rt.pos("azimuth", 45)
rt.pos("tilt", 30)

rt.jog("azimuth", 10)
rt.jog("tilt", -5)

rt.stop()
rt.disable()
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

- Cache de estado local (posição atual)
- Retry automático Modbus
- Streaming de telemetria
- Execução de scripts de movimento

# 👥 Equipe
**Roney e EFO-S**