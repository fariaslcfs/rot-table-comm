# 🛰️ Mesa Inercial 2 Eixos - Controle Web
![Python](/static/img/badge-python.svg) ![Flask](/static/img/badge-flask.svg) ![Modbus](/static/img/badge-modbus.svg) ![Status](/static/img/badge-status.svg)

Interface web para controle da **mesa inercial de 2 eixos Infax** (azimute + tilt) via protocolo **Modbus TCP**.

⚠️ Em ambientes **sem Internet**, os badges externos não serão exibidos. Utilize versões locais comentadas no topo do projeto.

---

# 📌 Visão Geral
Sistema completo de controle e monitoramento com backend em Flask, comunicação via Modbus TCP, interface web responsiva e simulador integrado para testes offline.

---

# 🚀 Características Principais
- Interface responsiva (**Bootstrap 5 + Chart.js**)
- Comunicação Modbus com retries automáticos e reconexão periódica
- Monitoramento em tempo real de posição e velocidade
- Gráficos dinâmicos com auto-scale
- Leitura atômica de registradores
- Modos de operação: posicionamento absoluto, jog manual, jog com rampa, execução de scripts
- Console de engenharia integrado
- Persistência em JSON e gravação de dados em TXT
- Logging rotativo e tratamento robusto de falhas
- Shutdown seguro
- Salvamento de scripts via Tkinter
- 🧪 Simulador Modbus integrado

---

# 🧪 Simulador Modbus (Testes Offline)
Servidor Modbus TCP local (simuladormesacomcomandos.py): `127.0.0.1:5020`

## Modos
- **Interativo** → valores definidos na inicialização
- **JSON** → carregamento automático via `mesa_config.json`

## Funcionalidades
- Simulação realista com aceleração, regime constante e desaceleração
- Inicialização configurável dos eixos
- Atualização dinâmica via `watchdog`
- Validação completa do backend sem hardware físico

## Dependência obrigatória
~~~bash
pip install watchdog
~~~

Sem o watchdog, não há atualização em runtime.

---

# 💻 Ambiente Suportado
- **Windows 10** → Desenvolvimento
- **Linux Mint 22 Cinnamon** → Produção
- **Python 3.12.x**

Comunicação validada com hardware real e simulador local.

---

# 📦 Instalação e Dependências
~~~bash
pip install flask pymodbus==3.12.0 watchdog --break-system-packages
~~~

## Tkinter (necessário para salvar arquivos)

### Linux
~~~bash
sudo apt install python3-tk
~~~

## Observação
Utiliza **pymodbus 3.x** (evitar código legado da versão 2.x).

---

# 🧪 Console de Engenharia

## Comandos básicos
~~~text
READ 72
WRITE 72 3000
R VPA
W VPA 30
~~~

---

# 🎮 Controle de Movimento

## 🔹 Jog (Velocidade Contínua)
~~~text
# Habilitar sistema
WRITE 22 1

# Configurar velocidade/aceleração
WRITE 72 1500
WRITE 74 6000
WRITE 62 1000
WRITE 64 5000

# Jog Azimute +
WRITE 56 500
WRITE 28 1

# Jog Azimute -
WRITE 56 300
WRITE 28 2

# Jog Tilt +
WRITE 46 200
WRITE 26 1

# Parar
WRITE 28 0
WRITE 26 0
~~~

## 🔹 Posicionamento Absoluto
~~~text
# Configuração dinâmica
WRITE 72 3000
WRITE 74 10000
WRITE 62 3000
WRITE 64 10000

# Posição alvo (32 bits)
WRITE 70 24464
WRITE 71 1

# Executar movimento
WRITE 28 4
WRITE 26 4
~~~

---

# 📊 Mapa Modbus

## 🔹 Input Registers (Somente leitura)
| Endereço | Conteúdo |
|----------|----------|
| 0-1 | POS_AZI (INT32) |
| 2-3 | VEL_AZI (INT32) |
| 4-5 | POS_TILT (INT32) |
| 6-7 | VEL_TILT (INT32) |

## 🔹 Holding Registers
| Endereço | Nome | Descrição |
|----------|------|----------|
| 22 | ENABLE | Habilitação geral |
| 28 | CMD_AZI | 0=stop, 1=+, 2=-, 4=pos |
| 26 | CMD_TILT | 0=stop, 1=+, 2=-, 4=pos |
| 46-47 | VEL_TILT_CMD | Velocidade Tilt |
| 56-57 | VEL_AZI_CMD | Velocidade Azimute |
| 60-61 | TARGET_TILT | Posição alvo Tilt |
| 70-71 | TARGET_AZI | Posição alvo Azimute |
| 72 | VPosAzi | Velocidade pos. Azimute |
| 74 | APosAzi | Aceleração Azimute |
| 62 | VPosTilt | Velocidade pos. Tilt |
| 64 | APosTilt | Aceleração Tilt |

---

# 🔄 Escalas e Conversões
- Input Registers → `valor / 1_000_000`
- Holding Registers → `valor / 100`
- Velocidade → `× 100`
- Posição → `× 1000`

## Conversão 32 bits
~~~python
LOW  = value & 0xFFFF
HIGH = value >> 16
~~~

Exemplo: `90000 → LOW = 24464 | HIGH = 1`

---

# 🔌 API HTTP (Flask)

## GET
~~~
/api/dados
~~~

## POST
~~~
/api/gravacao
/api/parar_gravacao
/api/emergencia
/api/reset
/api/posicionamento
/api/jog
/api/hab_jog
/api/des_jog
/api/jog_automatizada
/api/executa_script
/api/console
/api/salvar_local
~~~

## GET/POST
~~~
/api/config
~~~

---

# 📦 Build com PyInstaller

## Windows
~~~bash
pyinstaller interfacemesainfax.py --onefile --icon static/img/logoinfax.ico --add-data "static;static" --add-data "templates;templates"
~~~

## Linux
~~~bash
pyinstaller interfacemesainfax.py --onefile --icon static/img/logoinfax.ico --add-data "static:static" --add-data "templates:templates"
~~~

---

# 🧯 Troubleshooting
| Problema | Causa provável | Solução |
|----------|--------------|--------|
| Overflow 16 bits | Valor grande | Usar HIGH/LOW |
| Valor incorreto | Escala errada | Revisar fator |
| Falha Modbus | TCP/IP | Verificar conexão |
| Simulador não atualiza | watchdog ausente | Instalar dependência |
| Tkinter não abre | pacote ausente | instalar python3-tk |

---

# 🧠 Destaques Técnicos
- Arquitetura híbrida (hardware real + simulador)
- Atualização dinâmica via JSON + watchdog
- Leitura atômica Modbus
- Execução determinística de scripts
- Alta tolerância a falhas de comunicação
- Console de engenharia avançado

---

# 📄 Licença
Uso interno.

---

# 👥 Equipe
**EFO-S**