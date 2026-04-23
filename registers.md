## 🔹 Input Registers (Somente leitura)
| Endereço 16 bits | Conteúdo |
|----------|----------|
| 0-1 | POS_YAW |
| 2-3 | VEL_YAW |
| 4-5 | POS_ROLL |
| 6-7 | VEL_ROLL |

## 🔹 Holding Registers
| Endereço 16 bits | Nome | Descrição |
|----------|------|----------|
| 22 | ENABLE | Habilitação de ambos eixos |
| 24 | Sem função | Uso geral |
| 28 | CMD_YAW | 0=stop, 1=+, 2=-, 4=pos |
| 26 | CMD_ROLL | 0=stop, 1=+, 2=-, 4=pos |
| 46-47 | VEL_ROLL_CMD | Velocidade Roll |
| 56-57 | VEL_YAW_CMD | Velocidade Yaw |
| 60-61 | TARGET_ROLL | Posição alvo Roll |
| 70-71 | TARGET_YAW | Posição alvo Yaw |
| 72 | VPosYaw | Velocidade pos. Yaw |
| 74 | APosYaw | Aceleração Yaw |
| 62 | VPosRoll | Velocidade pos. Roll |
| 64 | APosRoll | Aceleração Roll |
| 80 | MaxVelRoll | Roll max velocity |
| 82 | MaxAccRoll | Roll max acceleration |
| 90 | MaxVelYaw | Yaw max velocity |
| 92 | MaxAccYaw | Yaw max acceleration |