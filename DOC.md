# Mesa Inercial IEAv — Controle via Modbus TCP (Python Interface)

## Visão Geral

Este documento descreve a interface de controle da mesa inercial de 2 eixos (Azimuth e Tilt) utilizada no IEAv, operando via protocolo **Modbus TCP**.

A abordagem substitui o sistema original em C (com dependência de compilação, Mongoose server e frontend JS) por uma solução direta em Python, simplificando manutenção, testes e integração.

### Parâmetros de conexão

- IP padrão do controlador: `192.168.1.1`
- Porta: `502`
- Protocolo: Modbus TCP

---

## Princípios de operação

- Todas as posições e velocidades são enviadas em **unidades de engenharia escaladas**
- Escalas utilizadas:
  - Velocidade: `valor × 100`
  - Posição: `valor × 1000`
- Registradores de 32 bits são divididos em dois registradores de 16 bits:
  - LOW = `value & 0xFFFF`
  - HIGH = `value >> 16`

---

## Estrutura de registradores (Controlador da mesa)

### Controle de movimento

| Endereço | Função | Descrição |
|----------|--------|-----------|
| 20 | Emergency Stop | 4 = stop imediato / 0 = reset |
| 22 | Enable Tilt | 0 off / 1 on / 2 reverse |
| 24 | Enable Azimuth | 0 off / 1 on |
| 26 | Tilt Command | 0 stop / 1 forward / 2 reverse |
| 28 | Azimuth Command | 0 stop / 1 forward / 2 reverse / 4 mode pos |

---

### Configuração de movimento (posicionamento)

| Endereço | Função |
|----------|--------|
| 40 | Tilt acceleration |
| 42 | Tilt max acceleration |
| 50 | Azimuth acceleration |
| 52 | Azimuth max acceleration |
| 60 | Tilt position (LOW/HIGH 32-bit) |
| 70 | Azimuth position (LOW/HIGH 32-bit) |

---

### Velocidade (jog / controle contínuo)

| Endereço | Função |
|----------|--------|
| 46 | Tilt velocity (32-bit) |
| 56 | Azimuth velocity (32-bit) |

---

### Limites e parâmetros adicionais

| Endereço | Função |
|----------|--------|
| 62 | Tilt velocity position |
| 64 | Tilt acceleration position |
| 72 | Azimuth velocity position |
| 74 | Azimuth acceleration position |
| 76 | Azimuth acceleration (extra) |
| 80 | Tilt max velocity |
| 82 | Tilt max acceleration |
| 90 | Azimuth max velocity |
| 92 | Azimuth max acceleration |

---

## Regras importantes de operação

### Sequência de posicionamento

Para garantir operação correta do controlador da mesa:

1. Habilitar eixo:
   - Tilt: `22 = 2`
   - Azimuth: `24 = 2`

2. Reset comando:
   - `26 = 0` (Tilt)
   - `28 = 0` (Azimuth)

3. Enviar posição (32 bits split)

4. Configurar aceleração

5. Ativar modo posição:
   - `26 = 4` (Tilt)
   - `28 = 4` (Azimuth)

---

### Sequência de velocidade (jog)

1. Configuração base:
   - `22 = 1`
   - `24 = 1`
   - `40 = 10000`
   - `42 = 10000`
   - `50 = 10000`
   - `52 = 10000`

2. Envio de velocidade:
   - Tilt: `46` (×100)
   - Azimuth: `56` (×100)

3. Direção:
   - 0 = stop
   - 1 = forward
   - 2 = reverse

---

## Formato de registradores 32 bits

Alguns registradores exigem divisão em dois registradores de 16 bits.

### Regra

~~~c
uint16_t LOW  = value & 0xFFFF;
uint16_t HIGH = value >> 16;
~~~

### Exemplo prático

Valor:

- 90000

Conversão:

- Hex: 0x00015F90

Resultado:

- LOW = 24464
- HIGH = 1

---

## Observações de protocolo

- O firmware original em C abre e fecha conexão Modbus a cada comando
- A implementação Python pode manter conexão persistente
- Alguns comandos exigem delays (~20ms) entre operações
- Comando de posição exige transição: 0 → 4

---

## Convenções físicas

- Azimuth = eixo horizontal (yaw)
- Tilt = eixo vertical (pitch)
- Posição: graus × 1000
- Velocidade: graus/s × 100

---

## Resumo operacional

### Movimentos suportados

- Posicionamento absoluto
- Jog contínuo
- Stop imediato
- Controle independente ou combinado de eixos

---

## Nota de engenharia

Este mapeamento foi obtido por engenharia reversa do controlador da mesa IEAv e validado empiricamente via Modbus TCP.

A arquitetura atual elimina dependências do sistema legado e permite controle direto via Python com comportamento equivalente ao firmware original.


# 👥 Equipe
**Roney e EFO-S**
