/* ============================================================
   TCC - Sistema de Monitoramento e Diagnóstico para Veículos
   Antigos Utilizando Análise Semanal de Dados
   Autor: Victor Vianelo Campos
   Plataforma: ESP32 (simulado no Wokwi)
   ------------------------------------------------------------
   O QUE ESTE CÓDIGO FAZ:
   1. Ao iniciar, mostra no Serial Monitor e no display um LOG
      FICTÍCIO de demonstração da "semana anterior", já com o
      diagnóstico OK / CUIDADO calculado - só para ilustrar o
      funcionamento antes mesmo da primeira semana real rodar.
   2. Lê 3 sensores (simulados por potenciômetros no Wokwi):
        - Temperatura do óleo   (°C)
        - Pressão do óleo       (bar)
        - Tensão elétrica       (V)
      e mostra os 3 valores em TEMPO REAL no display OLED.
   3. Registra 1 leitura por "dia simulado" (DURACAO_DIA_MS).
      Após 7 dias, gera um DIAGNÓSTICO SEMANAL no Serial Monitor
      e atualiza, no display, o status de cada sensor: "OK" ou
      "CUIDADO".
   4. Reinicia o ciclo para a semana seguinte.

   FAIXAS DE NORMALIDADE (definidas pelo autor do TCC):
      - Temperatura do óleo : média entre 90 °C e 105 °C
      - Pressão do óleo     : média em torno de 0,8 bar,
                              nunca abaixo de 0,3 bar
      - Tensão elétrica     : média entre 13,5 V e 14,5 V

   BIBLIOTECAS NECESSÁRIAS (aba "Library Manager"):
      - Adafruit GFX Library
      - Adafruit SSD1306

   LIGAÇÕES (veja diagram.json):
      - GPIO34 -> potenciômetro 1 (temperatura do óleo)
      - GPIO35 -> potenciômetro 2 (pressão do óleo)
      - GPIO32 -> potenciômetro 3 (tensão elétrica)
      - GPIO21 (SDA) / GPIO22 (SCL) -> display OLED (I2C)
   ============================================================ */

#include <Wire.h>
#include <math.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ---------------------- DISPLAY OLED -------------------------

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET   -1
#define OLED_ADDR    0x3C

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// ---------------------- CONFIGURAÇÕES -------------------------

#define PIN_TEMP_OLEO    34
#define PIN_PRESSAO_OLEO 35
#define PIN_TENSAO       32

// Duração de 1 "dia simulado", em milissegundos.
const unsigned long DURACAO_DIA_MS = 4000;

// Intervalo de atualização do display em tempo real (ms)
const unsigned long INTERVALO_DISPLAY_MS = 300;

const int DIAS_POR_SEMANA = 7;

// ---------------------- FAIXAS DE NORMALIDADE -------------------
// Definidas pelo autor do TCC para este sistema.

// Temperatura do óleo (°C) - média deve ficar entre 90 e 105
const float TEMP_OLEO_MEDIA_MIN = 90.0;
const float TEMP_OLEO_MEDIA_MAX = 105.0;

// Pressão do óleo (bar) - média em torno de 0,8, nunca abaixo de 0,3
const float PRESSAO_MEDIA_ALVO      = 0.8;
const float PRESSAO_MEDIA_TOLERANCIA = 0.3; // aceita média entre 0,5 e 1,1
const float PRESSAO_MINIMA_SEGURA    = 0.3; // se cair abaixo disso -> CUIDADO

// Tensão elétrica (V) - média deve ficar entre 13.5 e 14.5
const float TENSAO_MEDIA_MIN = 13.5;
const float TENSAO_MEDIA_MAX = 14.5;

// ---------------------- VARIÁVEIS DE CONTROLE -------------------

struct Leitura {
  float tempOleo;
  float pressaoOleo;
  float tensao;
};

Leitura semana[DIAS_POR_SEMANA];
int diaAtual = 0;
unsigned long ultimoDia = 0;
unsigned long ultimoDisplay = 0;
int numeroSemana = 1;

// Status persistido da última semana concluída (mostrado no display)
String statusTempDisplay    = "OK";
String statusPressaoDisplay = "OK";
String statusTensaoDisplay  = "OK";

void mostrarLogSemanaAnteriorFicticio();
void atualizarDisplay();
void coletarLeituraDoDia();
void lerSensoresAtuais(float &tempOleo, float &pressaoOleo, float &tensao);
float mapFloat(float x, float inMin, float inMax, float outMin, float outMax);
void gerarDiagnosticoSemanal();
String classificarTemperatura(float media);
String classificarPressao(float media, float minima);
String classificarTensao(float media);

// ---------------------- SETUP -----------------------------------

void setup() {
  Serial.begin(115200);
  delay(300);

  Wire.begin();
  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    Serial.println("Falha ao iniciar o display OLED!");
  }
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  Serial.println();
  Serial.println("=====================================================");
  Serial.println(" SISTEMA DE MONITORAMENTO - VEICULOS ANTIGOS (ESP32)");
  Serial.println("=====================================================");

  // Mostra um log fictício de demonstração, simulando a "semana anterior",
  // tanto no Serial Monitor quanto no display, antes de iniciar a coleta real.
  mostrarLogSemanaAnteriorFicticio();

  Serial.println("\nIniciando coleta diaria de sensores...\n");

  analogReadResolution(12); // ESP32: ADC de 12 bits (0-4095)

  ultimoDia = millis();
  ultimoDisplay = millis();
}

// ---------------------- LOOP PRINCIPAL ---------------------------

void loop() {
  // Atualiza o display em tempo real
  if (millis() - ultimoDisplay >= INTERVALO_DISPLAY_MS) {
    ultimoDisplay = millis();
    atualizarDisplay();
  }

  // Coleta 1 leitura por "dia simulado"
  if (millis() - ultimoDia >= DURACAO_DIA_MS) {
    ultimoDia = millis();
    coletarLeituraDoDia();
  }
}

// ---------------------- LEITURA DOS SENSORES ----------------------

void lerSensoresAtuais(float &tempOleo, float &pressaoOleo, float &tensao) {
  int leituraTempRaw    = analogRead(PIN_TEMP_OLEO);
  int leituraPressaoRaw = analogRead(PIN_PRESSAO_OLEO);
  int leituraTensaoRaw  = analogRead(PIN_TENSAO);

  tempOleo    = mapFloat(leituraTempRaw,    0, 4095, 40.0, 140.0);  // °C
  pressaoOleo = mapFloat(leituraPressaoRaw, 0, 4095, 0.0, 8.0);     // bar
  tensao      = mapFloat(leituraTensaoRaw,  0, 4095, 9.0, 16.0);    // V
}

void coletarLeituraDoDia() {
  float tempOleo, pressaoOleo, tensao;
  lerSensoresAtuais(tempOleo, pressaoOleo, tensao);

  semana[diaAtual].tempOleo    = tempOleo;
  semana[diaAtual].pressaoOleo = pressaoOleo;
  semana[diaAtual].tensao      = tensao;

  Serial.printf("[Semana %d | Dia %d/%d] Temp. óleo: %.1f °C | Pressão: %.2f bar | Tensão: %.2f V\n",
                numeroSemana, diaAtual + 1, DIAS_POR_SEMANA, tempOleo, pressaoOleo, tensao);

  diaAtual++;

  if (diaAtual >= DIAS_POR_SEMANA) {
    gerarDiagnosticoSemanal();
    diaAtual = 0;
    numeroSemana++;
  }
}

float mapFloat(float x, float inMin, float inMax, float outMin, float outMax) {
  return (x - inMin) * (outMax - outMin) / (inMax - inMin) + outMin;
}

// ---------------------- DISPLAY EM TEMPO REAL -----------------------

void atualizarDisplay() {
  float tempOleo, pressaoOleo, tensao;
  lerSensoresAtuais(tempOleo, pressaoOleo, tensao);

  display.clearDisplay();
  display.setCursor(0, 0);

  display.println("MONITOR - TEMPO REAL");
  display.println("--------------------");

  display.print("TEMP : ");
  display.print(tempOleo, 1);
  display.println(" C");

  display.print("PRESS: ");
  display.print(pressaoOleo, 2);
  display.println(" bar");

  display.print("VOLT : ");
  display.print(tensao, 2);
  display.println(" V");

  display.println("--------------------");
  display.print("SEMANA ");
  display.println(numeroSemana);

  display.print("T:");
  display.print(statusTempDisplay);
  display.print(" P:");
  display.print(statusPressaoDisplay);
  display.print(" V:");
  display.print(statusTensaoDisplay);

  display.display();
}

// ---------------------- REGRAS DE CLASSIFICAÇÃO (OK / CUIDADO) -----------------------

String classificarTemperatura(float media) {
  if (media >= TEMP_OLEO_MEDIA_MIN && media <= TEMP_OLEO_MEDIA_MAX) {
    return "OK";
  }
  return "CUIDADO";
}

String classificarPressao(float media, float minima) {
  if (minima < PRESSAO_MINIMA_SEGURA) {
    return "CUIDADO"; // caiu abaixo do minimo de seguranca
  }
  float desvio = fabs(media - PRESSAO_MEDIA_ALVO);
  if (desvio <= PRESSAO_MEDIA_TOLERANCIA) {
    return "OK";
  }
  return "CUIDADO";
}

String classificarTensao(float media) {
  if (media >= TENSAO_MEDIA_MIN && media <= TENSAO_MEDIA_MAX) {
    return "OK";
  }
  return "CUIDADO";
}

// ---------------------- LOG FICTÍCIO DA "SEMANA ANTERIOR" -----------------------
// Dados de demonstração (não vêm dos sensores) - apenas para ilustrar
// o funcionamento do diagnóstico antes da primeira semana real terminar.

void mostrarLogSemanaAnteriorFicticio() {
  // Valores fictícios de exemplo (média da semana anterior)
  float tempMediaFicticia    = 98.4;  // dentro da faixa (90-105) -> OK
  float pressaoMediaFicticia = 0.82;  // perto de 0.8            -> OK
  float pressaoMinimaFicticia = 0.35; // acima do minimo de 0.3  -> OK
  float tensaoMediaFicticia  = 14.0;  // dentro da faixa (13.5-14.5) -> OK

  String statusTemp    = classificarTemperatura(tempMediaFicticia);
  String statusPressao = classificarPressao(pressaoMediaFicticia, pressaoMinimaFicticia);
  String statusTensao  = classificarTensao(tensaoMediaFicticia);

  Serial.println("\n-----------------------------------------------------");
  Serial.println(" LOG DA SEMANA ANTERIOR (dados ficticios de demonstracao)");
  Serial.println("-----------------------------------------------------");
  Serial.printf("Temperatura do oleo - Media: %.1f C  -> %s\n", tempMediaFicticia, statusTemp.c_str());
  Serial.printf("Pressao do oleo     - Media: %.2f bar (min: %.2f bar) -> %s\n", pressaoMediaFicticia, pressaoMinimaFicticia, statusPressao.c_str());
  Serial.printf("Tensao eletrica     - Media: %.2f V  -> %s\n", tensaoMediaFicticia, statusTensao.c_str());
  Serial.println("-----------------------------------------------------");

  // Mostra o mesmo log no display por alguns segundos antes de iniciar
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("LOG SEMANA ANTERIOR");
  display.println("(dados ficticios)");
  display.println("--------------------");
  display.print("TEMP : ");
  display.print(tempMediaFicticia, 1);
  display.print(" -> ");
  display.println(statusTemp);
  display.print("PRESS: ");
  display.print(pressaoMediaFicticia, 2);
  display.print(" -> ");
  display.println(statusPressao);
  display.print("VOLT : ");
  display.print(tensaoMediaFicticia, 2);
  display.print(" -> ");
  display.println(statusTensao);
  display.display();

  delay(4000); // mantem o log visivel por 4 segundos antes de iniciar a coleta real
}

// ---------------------- DIAGNÓSTICO SEMANAL (DADOS REAIS DOS SENSORES) -----------------------

void gerarDiagnosticoSemanal() {
  float somaTemp = 0, somaPressao = 0, somaTensao = 0;
  float minPressao = semana[0].pressaoOleo, maxPressao = semana[0].pressaoOleo;
  float minTemp = semana[0].tempOleo, maxTemp = semana[0].tempOleo;
  float minTensao = semana[0].tensao, maxTensao = semana[0].tensao;

  for (int i = 0; i < DIAS_POR_SEMANA; i++) {
    somaTemp    += semana[i].tempOleo;
    somaPressao += semana[i].pressaoOleo;
    somaTensao  += semana[i].tensao;

    if (semana[i].tempOleo > maxTemp) maxTemp = semana[i].tempOleo;
    if (semana[i].tempOleo < minTemp) minTemp = semana[i].tempOleo;

    if (semana[i].pressaoOleo > maxPressao) maxPressao = semana[i].pressaoOleo;
    if (semana[i].pressaoOleo < minPressao) minPressao = semana[i].pressaoOleo;

    if (semana[i].tensao > maxTensao) maxTensao = semana[i].tensao;
    if (semana[i].tensao < minTensao) minTensao = semana[i].tensao;
  }

  float mediaTemp    = somaTemp / DIAS_POR_SEMANA;
  float mediaPressao = somaPressao / DIAS_POR_SEMANA;
  float mediaTensao  = somaTensao / DIAS_POR_SEMANA;

  String statusTemp    = classificarTemperatura(mediaTemp);
  String statusPressao = classificarPressao(mediaPressao, minPressao);
  String statusTensao  = classificarTensao(mediaTensao);

  statusTempDisplay    = statusTemp;
  statusPressaoDisplay = statusPressao;
  statusTensaoDisplay  = statusTensao;

  String statusGeral = (statusTemp == "OK" && statusPressao == "OK" && statusTensao == "OK") ? "OK" : "CUIDADO";

  Serial.println("\n=====================================================");
  Serial.printf("   DIAGNOSTICO SEMANAL - SEMANA %d\n", numeroSemana);
  Serial.println("=====================================================");

  Serial.println("-- Temperatura do óleo --");
  Serial.printf("Média: %.1f °C | Mínima: %.1f °C | Máxima: %.1f °C | Status: %s\n\n", mediaTemp, minTemp, maxTemp, statusTemp.c_str());

  Serial.println("-- Pressão do óleo --");
  Serial.printf("Média: %.2f bar | Mínima: %.2f bar | Máxima: %.2f bar | Status: %s\n\n", mediaPressao, minPressao, maxPressao, statusPressao.c_str());

  Serial.println("-- Tensão elétrica --");
  Serial.printf("Média: %.2f V | Mínima: %.2f V | Máxima: %.2f V | Status: %s\n\n", mediaTensao, minTensao, maxTensao, statusTensao.c_str());

  Serial.println("-----------------------------------------------------");
  Serial.printf("DIAGNOSTICO GERAL DO SISTEMA: %s\n", statusGeral.c_str());
  if (statusGeral == "CUIDADO") {
    Serial.println("-> Recomendação: verificar o(s) parâmetro(s) fora da faixa\n   e agendar inspeção preventiva.");
  } else {
    Serial.println("-> Recomendação: nenhuma ação necessária. Sistema operando\n   dentro dos parâmetros esperados nesta semana.");
  }
  Serial.println("=====================================================\n");
}