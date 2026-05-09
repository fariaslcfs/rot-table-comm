# RotTableWrapper (RotTableComm refatorada) — Classe de Controle da Mesa Inercial (Python 3.12.3, pymodbus 3.7.4)

Autor: Roney D. Silva e equipe EFO-S  

---

## 1. Visão Geral

A classe `RotTableWrapper` fornece uma interface de alto nível para controle de uma mesa inercial de dois eixos (**Yaw** e **Roll**) via protocolo **Modbus TCP**.

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

# Windows

- Python 3.12.3
- Observar a versão correta do pacote pymodbus (3.7.4), definida no requirements.txt.
- pip install -r requirements.txt --no-cache

# Linux Mint 22

- Python 3.12.3
- Observar a versão correta do pacote pymodbus (3.7.4), definida no requirements.txt.
- pip install -r requirements.txt --break-system-packages --no-cache


## 3. Conceitos Importantes

### 3.1 Registradores INT32 (2x16 bits)

O controlador da mesa utiliza registradores de 16 bits.  
Valores maiores (posição) são armazenados em 32 bits:

- valor (32 bits) = HIGH << 16 | LOW  (modbus é um protocolo de 16 bits)

---

### 3.2 Escalas

| Parâmetro  | Escala |
|------------|--------|
| Posição    | ×1000  |
| Velocidade | ×100   | 

Obs.:
Para a velocidade, 16 bits é suficiente porque o maior valor de velocidade será 500 °/s (500 x 100) que é 
menor que 65535

---


### Holding Registers (Controle)

| Addr | Função | Observação |             
|------|-

### Holding Registers (Controle)

| Addr | Função | Observação |             
|------|-### 3.3 Normalização de Ângulo

Todos os ângulos são convertidos para o intervalo:

~~~
[0, 360000]
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
| 0-1  | Yaw | Posição |
| 2-3  | Yaw | Velocidade |
| 4-5  | Roll    | Posição |
| 6-7  | Roll    | Velocidade |

---

### Holding Registers (Controle)

| Addr | Função | Observação |             
|------|--------|------------|
| 22   | Enable Roll |
| 24   | Enable Yaw |
| 26   | CMD Roll |
| 28   | CMD Yaw |
| 40   | Acc Roll |
| 42   | Max Acc Roll |
| 50   | Acc Yaw |
| 52   | Max Acc Yaw |
| 46-47| Vel Roll |    * O valor máximo de velocidade não ultrapassa 65535 (16 bits) usando somente 1 registrador (46) |
| 56-57| Vel Yaw |     * O valor máximo de velocidade não ultrapassa 65535 (16 bits) usando somente 1 registrador (56) |
| 60-61| Target Roll |     * Para o valor do target (posição angular de roll), 2 registradores de 16 bits são usados | 
| 70-71| Target Yaw |  * Para o valor do target (posição angular de yaw), 2 registradores de 16 bits são usados | 
| 80   | MaxVelRoll |      * Roll max velocity |
| 82   | MaxAccRoll |      * Roll max acceleration |
| 90   | MaxVelYaw |       * Yaw max velocity |
| 92   | MaxAccYaw |       * Yaw max acceleration |
---

## 5. Arquivo rotatorytable.py Refatorado

~~~

from pymodbus.client import ModbusTcpClient
import time
import json


SERVER_PROD = "192.168.1.1"
MODBUS_PORT_PROD = 502

SERVER_TEST = "127.0.0.1"
MODBUS_PORT_TEST = 5020

CONFIG_FILE = "mesa_config.json"


class RotTableWrapper:
    """
    =============================================================================
    RotTableWrapper — Interface de Controle de Mesa Inercial (YAW / ROLL)
    =============================================================================

    DESCRIÇÃO GERAL
    -------------------        print("RESET executado")
-----------------------------------------------------------------
    Esta classe encapsula (wrapper) o controle de uma mesa inercial de dois eixos (YAW e
    ROLL) através do protocolo Modbus TCP.

    O controlador utiliza registradores de 16 bits com suporte a valores de
    32 bits (DWORD) distribuídos em dois registradores consecutivos (LSB/MSB).

    A interface implementa três camadas:

        NÍVEL 1 — CORE         print("RESET executado")
MODBUS
            - write
            - write_dword
            - read_input
            - read_dword

        NÍVEL 2 — UTILITÁRIOS / CONFIGURAÇÃO
            - normalização
            - clipping
            - configuração persistente

        NÍVEL 3 — CONTROLE DE MOVIMENTO
            - prepare_*
            - move_*
            - jog_*
            - stop_*
            - get_*

    ---------------------------------------------------------------------------
    ESCALAS DO SISTEMA
    ---------------------------------------------------------------------------

    Escrita:
        - Velocidade → valor * 100
        - Posição    → valor * 1000

    Leitura:
        - Posição    → valor / 1_000_000
        - Velocidade → valor / 1_000_000

    ---------------------------------------------------------------------------
    MAPA DE REGISTRADORES (RESUMO)
    ---------------------------------------------------------------------------

    YAW:
        24 → modo/habilitação
        28 → trigger/comando
        56 → velocidade (DWORD)
        70 → posição (DWORD)

    ROLL:
        22 → modo/habilitação
        26 → trigger/comando
        46 → velocidade (DWORD)
        60 → posição (DWORD)

    FEEDBACK:
        0-1 → posição YAW (DWORD)
        2-3 → velocidade YAW (DWORD)
        4-5 → posição ROLL (DWORD)
        6-7 → velocidade ROLL (DWORD)

    CONTROLE GLOBAL:
        20 → comandos especiais (apply config / emergency)

    ---------------------------------------------------------------------------
    FLUXO DE COMANDOS (OBRIGATÓRIO)
    ---------------------------------------------------------------------------

    MOVE:
        prepare → mode → write position → delay → trigger

    JOG:
        prepare → write velocity → direction

    STOP:
        write(direction=0)

    READ:
        read → combine → convert → return

    ---------------------------------------------------------------------------
    OBSERVAÇÕES CRÍTICAS
    ---------------------------------------------------------------------------

    - Delays de 0.1 s são OBRIGATÓRIOS na preparação
    - Delay de 0.02 s é OBRIGATÓRIO antes do trigger de posição
    - Ordem de escrita influencia diretamente o comportamento
    - Escrita de DWORD deve respeitar ordem LSB → MSB
    - Sistema não valida automaticamente consistência de estados

    =============================================================================
    """

    def __init__(self, host=SERVER_PROD, port=MODBUS_PORT_PROD):
        """
        Inicializa o cliente Modbus TCP e configura o estado inicial da mesa inercial.

        Este método executa as seguintes etapas:

        --------------------------------------------------------------------
        1. CRIAÇÃO DO CLIENTE MODBUS
        --------------------------------------------------------------------
        Instancia um cliente Modbus TCP usando pymodbus, apontando para
        o endereço IP e porta definidos.

        Não estabelece conexão automaticamente — isso deve ser feito via connect().

        --------------------------------------------------------------------
        2. INICIALIZAÇÃO DAS CONFIGURAÇÕES INTERNAS
        --------------------------------------------------------------------
        Define os parâmetros padrão de operação da mesa inercial:

        - Aceleração (YAW / ROLL)
        - Aceleração máxima
        - Velocidade de movimento
        - Velocidade máxima

        Esses valores são mantidos como atributos públicos e podem ser:

        - Alterados diretamente
        - Modificados via métodos set_*
        - Persistidos em arquivo JSON

        --------------------------------------------------------------------
        3. FATOR DE ESCALA
        --------------------------------------------------------------------
        FACTOR = 100

        Usado para conversão de unidades entre o sistema de alto nível (graus)
        e os registradores Modbus do controlador.

        Exemplo:
            10.5 °/s → 1050 no registrador

        --------------------------------------------------------------------
        4. INTERAÇÃO COM O USUÁRIO (CONFIGURAÇÃO INICIAL)
        --------------------------------------------------------------------

        Durante a inicialização, o usuário é consultado via terminal:

        PASSO 1 — Salvar configuração padrão em arquivo JSON
            Pergunta:
                "Deseja salvar a configuração padrão da mesa no arquivo mesa_config.json? (s/N)"

            Se 's':
                → save_configToFile()

        PASSO 2 — Exibir configuração atual
            Mostra todos os parâmetros configurados no objeto

        PASSO 3 — Aplicar configuração na mesa física
            Pergunta:
                "Deseja enviar a configuração atual para a mesa? (s/N)"

            Se 's':
                → apply_configToTable()

        --------------------------------------------------------------------
        5. OBSERVAÇÕES IMPORTANTES
        --------------------------------------------------------------------
        - O método ensure() é chamado internamente para garantir que a conexão Modbus 
          esteja ativa antes de qualquer operação de leitura ou escrita. Assim, não é
          preciso chamar o método connect() explicitamente antes de executar qualquer
          método de comando para a mesa.
        - A interação usa input() → comportamento bloqueante
        - Ideal para modo CLI / testes manuais
        - NÃO recomendado para aplicações automatizadas ou GUIs
        - Em produção, recomenda-se remover ou parametrizar esse comportamento

        --------------------------------------------------------------------
        Parameters
        ----------
        host : str
            Endereço IP do controlador Modbus TCP.

        port : int
            Porta TCP do serviço Modbus.

        --------------------------------------------------------------------
        Attributes criados
        -----------------
        client : ModbusTcpClient
            Cliente Modbus

        # MAPA INTERNO (SAÍDA DE DADOS MODBUS)
        self._ADDR_YAW_POS  = 0
        self._ADDR_YAW_VEL  = 2
        self._ADDR_ROLL_POS = 4
        self._ADDR_ROLL_VEL = 6

        FACTOR : int
            Fator de escala

        yaw_acceleration_value : int
        roll_acceleration_value : int
        yaw_max_acceleration_value : int
        roll_max_acceleration_value : int
        yaw_move_velocity_value : int
        roll_move_velocity_value : int
        yaw_move_max_velocity_value : int
        roll_move_max_velocity_value : int
        """

        # =========================
        # CLIENT MODBUS
        # =========================
        self.client = ModbusTcpClient(host=host, port=port)

        # =========================
        # ESCALA
        # =========================
        self.FACTOR = 100

        # =========================
        # CONFIGURAÇÃO PADRÃO
        # =========================
        self.yaw_acceleration_value = int(100.0)
        self.roll_acceleration_value = int(100.0)

        self.yaw_max_acceleration_value = int(100.0)
        self.roll_max_acceleration_value = int(100.0)

        self.yaw_move_velocity_value = int(30.0)
        self.roll_move_velocity_value = int(30.0)

        self.yaw_move_max_velocity_value = int(500.0)
        self.roll_move_max_velocity_value = int(200.0)

        # MAPA INTERNO (SAÍDA DE DADOS MODBUS)
        self._ADDR_YAW_POS  = 0
        self._ADDR_YAW_VEL  = 2
        self._ADDR_ROLL_POS = 4
        self._ADDR_ROLL_VEL = 6

        # =====================================================
        # INTERAÇÃO: SALVAR CONFIG
        # =====================================================
        print("Deseja salvar a configuração padrão da mesa no arquivo mesa_config.json? (s/N)")
        choice = input().strip().lower()

        if choice == "":
            choice = "n"

        if choice == "s":
            self.save_configToFile()

        # =====================================================
        # EXIBE CONFIGURAÇÃO ATUAL
        # =====================================================

        print("Deseja ver a configuração padrão da mesa? (s/N)")
        choice = input().strip().lower()
        if choice == "":
            choice = "n"
        if choice == "s":
            print("\nCONFIGURAÇÃO ATUAL DA MESA INERCIAL")
            print(f"YAW_ACC={self.yaw_acceleration_value:.2f} °/s²")
            print(f"ROLL_ACC={self.roll_acceleration_value:.2f} °/s²")
            print(f"YAW_MAX_ACC={self.yaw_max_acceleration_value:.2f} °/s²")
            print(f"ROLL_MAX_ACC={self.roll_max_acceleration_value:.2f} °/s²")
            print(f"YAW_MOVE_VEL={self.yaw_move_velocity_value:.2f} °/s")
            print(f"ROLL_MOVE_VEL={self.roll_move_velocity_value:.2f} °/s")
            print(f"YAW_MAX_VEL={self.yaw_move_max_velocity_value:.2f} °/s")
            print(f"ROLL_MAX_VEL={self.roll_move_max_velocity_value:.2f} °/s")

        # =====================================================
        # INTERAÇÃO: APLICAR CONFIG
        # =====================================================
        print("\nDeseja enviar a configuração atual para a mesa? (s/N)")
        choice = input().strip().lower()

        if choice == "":
            choice = "n"

        if choice == "s":
            self.apply_configToTable()

    # =====================================================
    # CONNECTION
    # =====================================================

    def connect(self):
        """
        Estabelece conexão TCP com o servidor Modbus.

        Returns
        -------
        bool
            True se a conexão foi estabelecida com sucesso, False caso contrário.

        Observações
        -----------
        - Deve ser chamado antes de qualquer operação Modbus.
        - Em caso de falha, métodos subsequentes podem lançar erro.
        """
        return self.client.connect()

    def close(self):
        """
        Encerra a conexão TCP com o servidor Modbus.

        Observações
        -----------
        - Após chamada, qualquer operação requer nova conexão.
        """
        self.client.close()

    def _ensure(self):
        """
        Garante que a conexão Modbus esteja ativa.

        Comportamento
        -------------
        - Se não estiver conectado, tenta reconectar automaticamente.
        - Não lança exceção diretamente.

        Uso Interno
        -----------
        Chamado por todos os métodos de I/O Modbus.
        """
        if not self.client.connected:
            self.client.connect()

    # =====================================================
    # CORE MODBUS
    # =====================================================

    def write(self, addr, value):
        """
        Escreve um valor em um registrador holding (16 bits).

        Parameters
        ----------
        addr : int
            Endereço do registrador.
        value : int
            Valor inteiro a ser escrito.

        Returns
        -------
        ModbusResponse

        Notas
        -----
        - Valor é convertido para inteiro.
        - Não realiza validação de faixa.
        - Operação síncrona.
        """
        self._ensure()
        return self.client.write_register(addr, int(value))

    def write_dword(self, addr, value):
        """
        Escreve um valor de 32 bits (DWORD) em dois registradores consecutivos.

        Estrutura:
            addr     → LSB
            addr + 1 → MSB

        Parameters
        ----------
        addr : int
            Endereço base (LSB).
        value : int
            Valor inteiro de 32 bits.

        Observações
        -----------
        - Ordem de escrita: LSB → MSB (OBRIGATÓRIO)
        - Não há atomicidade (duas operações separadas)
        """

        value = int(value)
        low = value & 0xFFFF
        high = (value >> 16) & 0xFFFF

        self.write(addr, low)
        self.write(addr + 1, high)

    def read_input(self, addr, count=2):
        """
        Lê registradores de entrada (Input Registers).

        Parameters
        ----------
        addr : int
            Endereço inicial.
        count : int
            Quantidade de registradores a serem lidos.

        Returns
        -------
        ModbusResponse

        Notas
        -----
        - Não realiza parsing automático.
        - Deve ser tratado externamente.
        """
        self._ensure()
        return self.client.read_input_registers(addr, count=count)

    def read_dword(self, addr):
        """
        Lê um valor de 32 bits a partir de dois registradores.

        Parameters
        ----------
        addr : int
            Endereço base (LSB).

        Returns
        -------
        int or None

        Fluxo
        -----
        read_input → combine → return
        """
        r = self.read_input(addr, 2)
        if r.isError():
            return None
        return (r.registers[1] << 16) | r.registers[0]

    # =====================================================
    # UTILITÁRIOS
    # =====================================================

    def to_int32(self, raw):
        """
        Converte valor de 32 bits sem sinal para inteiro com sinal.

        Parameters
        ----------
        raw : int

        Returns
        -------
        int

        Detalhes
        --------
        - Usa complemento de dois
        - Necessário para interpretar valores negativos vindos do controlador
        """
        return raw - 0x100000000 if raw & 0x80000000 else raw

    def normalize(self, deg):
        """
        Normaliza ângulo para formato esperado pelo controlador.

        Parameters
        ----------
        deg : float

        Returns
        -------
        int

        Regras
        ------
        - Converte para escala interna (*1000)
        - Evita valores negativos usando espelhamento
        """
        v = int(deg * 1000)
        return 360000 - abs(v) if v < 0 else v

    def _read_int32(self, addr):
        """
        Lê um valor de 32 bits (2 registradores Modbus) e converte para inteiro com sinal.

        --------------------------------------------------------------------
        DESCRIÇÃO
        --------------------------------------------------------------------
        Executa uma leitura de 2 registradores consecutivos (16 bits cada),
        combinando-os em um valor de 32 bits no formato:

            raw = (MSB << 16) | LSB

        Em seguida, converte o valor para inteiro com sinal utilizando
        representação em complemento de dois.

        --------------------------------------------------------------------
        PARÂMETROS
        --------------------------------------------------------------------
        addr : int
            Endereço base (LSB) do valor 32 bits.

        --------------------------------------------------------------------
        RETORNO
        --------------------------------------------------------------------
        int | None
            Valor convertido (com sinal), ou None em caso de erro de leitura.

        --------------------------------------------------------------------
        OBSERVAÇÕES
        --------------------------------------------------------------------
        - Esta função NÃO aplica escala (ex: divisão por 1_000_000)
        - Deve ser usada como primitiva interna (Layer 2)
        - Centraliza a lógica de parsing Modbus → reduz duplicação
        """

        rr = self.read_input(addr, 2)

        if rr.isError():
            return None

        raw = (rr.registers[1] << 16) | rr.registers[0]
        return self.to_int32(raw)

    # =====================================================
    # CONFIGURAÇÃO E PERSISTÊNCIA
    # =====================================================

    def set_config(self):
        """
        Aplica configuração completa ao controlador e persiste em arquivo.

        Fluxo:
            apply_configToTable → save_configToFile

        Observações
        -----------
        - Deve ser chamado após alteração de parâmetros internos
        """
        self.apply_configToTable()
        self.save_configToFile()

    def apply_configToTable(self):
        """
        Escreve parâmetros de movimento nos registradores e aplica configuração.

        Registradores utilizados
        ------------------------
        YAW:
            50, 52, 72, 90

        ROLL:
            40, 42, 62, 80

        Controle:
            20 → comando apply

        Sequência
        ---------
        write parâmetros → trigger apply → delay → reset
        """

        self.write(50, self.yaw_acceleration_value * self.FACTOR)
        self.write(52, self.yaw_max_acceleration_value * self.FACTOR)
        self.write(72, self.yaw_move_velocity_value * self.FACTOR)
        self.write(90, self.yaw_move_max_velocity_value * self.FACTOR)

        self.write(40, self.roll_acceleration_value * self.FACTOR)
        self.write(42, self.roll_max_acceleration_value * self.FACTOR)
        self.write(62, self.roll_move_velocity_value * self.FACTOR)
        self.write(80, self.roll_move_max_velocity_value * self.FACTOR)

        self.write(20, 2)
        time.sleep(1)
        self.write(20, 0)

    def save_configToFile(self):
        """
        Persiste configuração atual em arquivo JSON.

        Estrutura
        ---------
        Inclui:
            - parâmetros de posição
            - aceleração
            - velocidade máxima

        Caminho
        -------
        CONFIG_FILE

        Observações
        -----------
        - Sobrescreve arquivo existente
        - Não valida permissões
        """

        data = {
            "velPosAzimute": self.yaw_move_velocity_value,
            "velPosTilt": self.roll_move_velocity_value,
            "accPosAzimute": self.yaw_acceleration_value,
            "accPosTilt": self.roll_acceleration_value,
            "maxVelAzimute": self.yaw_move_max_velocity_value,
            "maxVelTilt": self.roll_move_max_velocity_value,
            "maxAccAzimute": self.yaw_max_acceleration_value,
            "maxAccTilt": self.roll_max_acceleration_value
        }

        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=4)

    # =====================================================
    # PREPARAÇÃO PARA MOVIMENTO
    # =====================================================

    def prepare_yaw_motion(self):
        """
        Prepara eixo YAW para movimento.

        Sequência obrigatória:
            write(acc)
            write(max_acc)
            enable roll
            delay 0.1
            enable yaw
            delay 0.1
        """

        self.write(40, int(self.yaw_acceleration_value * self.FACTOR))
        self.write(42, int(self.yaw_max_acceleration_value * self.FACTOR))

        self.write(22, 1)
        time.sleep(0.1)

        self.write(24, 1)
        time.sleep(0.1)

    def prepare_roll_motion(self):
        """
        Prepara eixo ROLL para movimento.

        Mesma lógica de dependência do YAW.
        """

        self.write(50, int(self.roll_acceleration_value * self.FACTOR))
        self.write(52, int(self.roll_max_acceleration_value * self.FACTOR))

        self.write(22, 1)
        time.sleep(0.1)

        self.write(24, 1)
        time.sleep(0.1)

    def prepare_all_motion(self):
        """
        Prepara ambos os eixos sequencialmente.

        Ordem:
            YAW → ROLL
        """
        self.prepare_yaw_motion()
        self.prepare_roll_motion()

    # =====================================================
    # JOG - VELOCIDADE CONTÍNUA
    # =====================================================

    def jog_yaw(self, vel):
        """
        Executa movimento contínuo (modo JOG) no eixo YAW.

        Parameters
        ----------
        vel : float
            Velocidade em °/s * 100 (FACTOR)

        Sequência:
            prepare → write velocity → trigger direction

        Registradores:
            56 → velocidade
            28 → direção e trigger (1=positivo, 2=negativo, 0=stop)
        """
        self.prepare_yaw_motion()
        self.write(56, abs(int(vel * self.FACTOR)))
        self.write(28, 1 if vel > 0 else 2 if vel < 0 else 0)

    def jog_roll(self, vel):
        """
        Executa movimento contínuo (modo JOG) no eixo ROLL.

        Parameters
        ----------
        vel : float
            Velocidade em °/s * 100 (FACTOR)

        Sequência:
            prepare → write velocity → trigger direction

        Registradores:
            46 → velocidade
            26 → direção e trigger (1=positivo, 2=negativo, 0=stop)
        """
        self.prepare_roll_motion()
        self.write(46, abs(int(vel * self.FACTOR)))
        self.write(26, 1 if vel > 0 else 2 if vel < 0 else 0)

    def jog_all(self, vel):
        """
        Movimento contínuo simultâneo YAW + ROLL.

        Parameters
        ----------
        vel : float
            Velocidade em °/s * 100 (FACTOR)
        """
        self.jog_yaw(vel)
        self.jog_roll(vel)

    # =====================================================
    # MOVE - POSICIONAMENTO ABSOLUTO
    # =====================================================

    def move_yaw(self, angle):
        """
        Movimento absoluto YAW.

        Parameters
        ----------
        angle : float
            Posicão em graus
        
        Sequência:
            prepare → mode → stop → write pos → delay → trigger
        """

        self.prepare_yaw_motion()

        self.write(24, 2)
        self.write(28, 0)

        self.write_dword(70, self.normalize(angle))

        time.sleep(0.02)
        self.write(28, 4)

    def move_roll(self, angle):
        """
        Movimento absoluto ROLL.

        Parameters
        ----------
        angle : float
            Posicão em graus
        
        Sequência:
            prepare → mode → stop → write pos → delay → trigger
        """

        self.prepare_roll_motion()

        self.write(22, 2)
        self.write(26, 0)

        self.write_dword(60, self.normalize(angle))

        time.sleep(0.02)
        self.write(26, 4)

    def move_all(self, angle):
        """
        Movimento absoluto simultâneo.

        Importante:
            Ambos os eixos são disparados quase simultaneamente.

        Parameters
        ----------
        angle : float
            Posição em graus
        
        Sequência:
            prepare → mode → stop → write pos → delay → trigger
        """

        self.prepare_all_motion()

        self.write(24, 2)
        self.write(22, 2)

        self.write(28, 0)
        self.write(26, 0)

        self.write_dword(70, self.normalize(angle))
        self.write_dword(60, self.normalize(angle))

        time.sleep(0.02)

        self.write(28, 4)
        self.write(26, 4)

    # =====================================================
    # STOP
    # ======================i===============================

    def stop_yaw(self):
        """
        Para imediatamente o eixo YAW.

        Método atua apenas zerando o registrador de direção.
        """
        self.write(28, 0)

    def stop_roll(self):
        """
        Para eixo ROLL.
        """
        self.write(26, 0)

    def stop_all(self):
        """
        Para ambos os eixos simultaneamente.
        """
        self.stop_yaw()
        self.stop_roll()

    # =====================================================
    # FEEDBACK — POSIÇÃO
    # =====================================================

    def get_pos_yaw(self):
        """
        Retorna a posição do eixo YAW em graus.

        --------------------------------------------------------------------
        DESCRIÇÃO
        --------------------------------------------------------------------
        Lê o valor bruto de posição do eixo YAW (32 bits) a partir do mapa
        interno de registradores e converte para unidade física (graus).

        Conversão aplicada:
            posição = valor_bruto / 1_000_000

        --------------------------------------------------------------------
        RETORNO
        --------------------------------------------------------------------
        float | None
            Posição YAW em graus, ou None em caso de erro.

        --------------------------------------------------------------------
        OBSERVAÇÕES
        --------------------------------------------------------------------
        - Não expõe endereços Modbus
        - Usa função interna _read_int32()
        - Conversão com sinal preservada
        """

        v = self._read_int32(self._ADDR_YAW_POS)
        return None if v is None else v / 1_000_000

    def get_pos_roll(self):
        """
        Retorna a posição do eixo ROLL em graus.

        --------------------------------------------------------------------
        DESCRIÇÃO
        --------------------------------------------------------------------
        Equivalente ao método get_pos_yaw(), aplicado ao eixo ROLL.

        Conversão aplicada:
            posição = valor_bruto / 1_000_000

        --------------------------------------------------------------------
        RETORNO
        --------------------------------------------------------------------
        float | None
            Posição ROLL em graus, ou None em caso de erro.

        --------------------------------------------------------------------
        OBSERVAÇÕES
        --------------------------------------------------------------------
        - Mantém simetria com eixo YAW
        """

        v = self._read_int32(self._ADDR_ROLL_POS)
        return None if v is None else v / 1_000_000

    def get_pos_all(self):
        """
        Retorna simultaneamente as posições dos eixos YAW e ROLL.

        --------------------------------------------------------------------
        DESCRIÇÃO
        --------------------------------------------------------------------
        Executa duas leituras independentes:

            YAW  → get_pos_yaw()
            ROLL → get_pos_roll()

        --------------------------------------------------------------------
        RETORNO
        --------------------------------------------------------------------
        tuple
            (yaw, roll) em graus

        --------------------------------------------------------------------
        OBSERVAÇÕES
        --------------------------------------------------------------------
        - Não é uma leitura atômica (duas requisições Modbus)
        - Pode haver pequeno desvio temporal entre eixos
        """

        return (
            self.get_pos_yaw(),
            self.get_pos_roll()
        )

    # =====================================================
    # FEEDBACK — VELOCIDADE
    # =====================================================

    def get_vel_yaw(self):
        """
        Retorna a velocidade do eixo YAW em graus por segundo (°/s).

        --------------------------------------------------------------------
        DESCRIÇÃO
        --------------------------------------------------------------------
        Lê o valor bruto de velocidade (32 bits) do eixo YAW e aplica
        conversão para unidade física.

        Conversão:
            velocidade = valor_bruto / 1_000_000

        --------------------------------------------------------------------
        RETORNO
        --------------------------------------------------------------------
        float | None
            Velocidade YAW em °/s, ou None em caso de erro.

        --------------------------------------------------------------------
        OBSERVAÇÕES
        --------------------------------------------------------------------
        - Sinal indica direção do movimento
        - Valor zero indica eixo parado
        """
        v = self._read_int32(self._ADDR_YAW_VEL)
        return None if v is None else v / 1_000_000

    def get_vel_roll(self):
        """
        Retorna a velocidade do eixo ROLL em graus por segundo (°/s).

        --------------------------------------------------------------------
        DESCRIÇÃO
        --------------------------------------------------------------------
        Equivalente ao método get_vel_yaw(), aplicado ao eixo ROLL.

        Conversão:
            velocidade = valor_bruto / 1_000_000

        --------------------------------------------------------------------
        RETORNO
        --------------------------------------------------------------------
        float | None
            Velocidade ROLL em °/s, ou None em caso de erro.
        """

        v = self._read_int32(self._ADDR_ROLL_VEL)
        return None if v is None else v / 1_000_000

    def get_vel_all(self):
        """
        Retorna simultaneamente as velocidades dos eixos YAW e ROLL.

        --------------------------------------------------------------------
        DESCRIÇÃO
        --------------------------------------------------------------------
        Executa duas leituras independentes:

            YAW  → get_vel_yaw()
            ROLL → get_vel_roll()

        --------------------------------------------------------------------
        RETORNO
        --------------------------------------------------------------------
        tuple
            (vel_yaw, vel_roll) em °/s

        --------------------------------------------------------------------
        OBSERVAÇÕES
        --------------------------------------------------------------------
        - Não é leitura síncrona
        - Pode haver defasagem temporal entre eixos
        """

        return (
            self.get_vel_yaw(),
            self.get_vel_roll()
        )
        # =====================================================
        # EMERGENCY
        # =====================================================

    def emergency_stop(self):
        """
        Executa parada de emergência via registrador de controle global.

        Sequência:
            write(20, 4) → delay → write(20, 0)
        """
        self.write(20, 4)
        time.sleep(1)
        self.write(20, 0)
        time.sleep(1)

    def emergency_reset(self):
        """
        Reseta estado de emergência do sistema.

        Sequência:
            Deve ser usado dentro do loop de tentativas
            delay deve ser de 1 segundo.
            write(20, 1) → delay → write(20, 0)
        """
        for _ in range(2):
            self.write(20, 1)
            time.sleep(1)
            self.write(20, 0)
            time.sleep(1)
            self.write(24, 0)
            self.write(22, 0)
                    
~~~

---



## 6. Observações de Engenharia

- `time.sleep(0.02)` é obrigatório para sincronização do controlador da mesa
- Registradores devem ser escritos na ordem correta:
  1. Enable
  2. Reset comando
  3. Escrita de posição/velocidade
  4. Start comando
- Yaw e Roll são independentes, mas compartilham o mesmo barramento lógico
- Falha em sequência pode gerar comportamento indeterminado no movimento

---

## 7. Ponto Crítico

O controlador da mesa NÃO aceita diretamente valores fora da escala:

- Posicionamento: sempre ×1000
- Velocidade: sempre ×100
- INT32 deve ser sempre dividido em LOW/HIGH

---

## 8. Extensões Futuras

- Retry automático Modbus
- Execução de scripts de movimento

# 👥 Equipe
**Roney e EFO-S**