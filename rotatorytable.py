from pymodbus.client import ModbusTcpClient
import time


class RotTableWrapper:
    """
    Wrapper estável para controle da mesa inercial IEAv
    via Modbus TCP (pymodbus 3.x+ / 4.x compatível).

    Foco: simplicidade de uso em laboratório.
    """

    def __init__(self, host="127.0.0.1", port=5020):
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
    # CORE MODBUS
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

    # =====================================================
    # UTILITÁRIO
    # =====================================================

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

    def azimuth_velocity(self, value: float):

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

    def tilt_velocity(self, value: float):

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

    def jog(self, axis: str, velocity: float):
        if axis.lower() == "azimuth":
            self.azimuth_velocity(velocity)
        elif axis.lower() == "tilt":
            self.tilt_velocity(velocity)
        elif axis.lower() == "both":
            self.azimuth_velocity(velocity)
            self.tilt_velocity(velocity)

    # =====================================================
    # POSIÇÃO
    # =====================================================

    def azimuth_position(self, angle: float):

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

    def tilt_position(self, angle: float):

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

    def pos(self, axis: str, angle: float):
        if axis.lower() == "azimuth":
            self.azimuth_position(angle)
        elif axis.lower() == "tilt":
            self.tilt_position(angle)
        elif axis.lower() == "both":
            self.azimuth_position(angle)
            self.tilt_position(angle)

    # =====================================================
    # LEITURA (FEEDBACK)
    # =====================================================

    def get_azimuth(self):
        r = self.read_input(0, 2)
        if r.isError():
            return None
        return ((r.registers[1] << 16) + r.registers[0]) / 1_000_000

    def get_tilt(self):
        r = self.read_input(4, 2)
        if r.isError():
            return None
        return ((r.registers[1] << 16) + r.registers[0]) / 1_000_000