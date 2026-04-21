# RotTableWrapper— Guia Rápido (Cheat Sheet)

> Controle da mesa inercial IEAv (Azimuth + Tilt) via Modbus TCP  
> Uso direto para testes e scripts simples

---

# 1. INICIALIZAÇÃO

~~~
Real
 - RotTableWrapper(host="192.168.1.1", port=502)

Com simulador
 - RotTableWrapper(host="127.0.0.1", port=5020)
~~~

Cria interface com a mesa ou simulador.

---

# 2. CONEXÃO

~~~
connect()
~~~
Abre comunicação Modbus TCP.

~~~
close()
~~~
Encerra comunicação.

---

# 3. HABILITAR / PARAR

~~~
enable()
~~~
Ativa Azimuth + Tilt.

~~~
disable()
~~~
Desativa sistema.

~~~
stop()
~~~
Para todos os movimentos imediatamente.

---

# 4. POSIÇÃO (ABSOLUTA)

~~~
posazi(angulo)
postilt(angulo)
pos(angulo)
~~~

Exemplo:
- posazi(45) → move Azimuth para 45°
- postilt(10) → move Tilt para 10°
- pos(22.4) → move ambos eixos para 22.4 °

---

# 5. JOG (VELOCIDADE)

~~~
jogazi(velocidade)
jogtilt(velocidade)
jog(velocidade)
~~~

Exemplo:
- jogazi(20) → inicia o giro contínuo do eixo Azi com velocidade de  20 °/s (girando no sentido positivo)
- jogtilt(-15) → inicia o giro contínuo do eixo Tilt com velocidade de 15 °/s (girando no sentido negativo)
- jog(45.5) → inicia o giro contínuo de ambos eixos com velocidade de 45.5 °/s (girando no sentido positivo)

---

# 6. LEITURA (FEEDBACK)

~~~
getposazi()
~~~
Retorna posição atual do Azimuth (graus)

~~~
getpostilt()
~~~
Retorna posição atual do Tilt (graus)

~~~
getpos()
~~~
Retorna posição atual de ambos eixos AZI e Tilt (graus)


---

# 7. REGRAS IMPORTANTES

- Valores de posição: graus
- Velocidade: graus/s
- Controle usa Modbus TCP
- Sempre chamar `enable()` antes de mover
- Usar `stop()` para interromper movimento

---

# 8. EXEMPLO MÍNIMO

~~~
rot = RotTableWrapper("127.0.0.1", 5020)

rot.connect()
rot.enable()

rot.posazi(30)
rot.postilt(10)
rot.pos(90.3)

rot.jogazi(30)
rot.jogtilt(22)
rot.jog(44)

rot.stop()
rot.close()
~~~

---

# 9. RESUMO

| Ação | Função |
|------|--------|
| Habilitar | enable() |
| Parar | stop() |
| Posicionar | pos(axis, angle) |
| Girar | jog(axis, velocity) |
| Ler posição | get_azimuth(), get_tilt() |

---