/**
 * @file app_config.h
 * @brief Deney standardı sabitleri. Senaryolar arası karşılaştırmada DEĞİŞTİRİLMEZ.
 *
 * Kaynak: hafta-01/docs/gereksinim.md §3 (çalışma koşulları).
 */
#ifndef APP_CONFIG_H
#define APP_CONFIG_H

#include "FreeRTOS.h"

#define APP_FW_VERSION          "hafta01-1.1.0"

/* ---- Görev öncelikleri: preemptive, 3 > 2 > 1 (Idle = 0) ---- */
#define PRIO_TELEMETRY          (tskIDLE_PRIORITY + 3)   /* Yüksek */
#define PRIO_BUTTON             (tskIDLE_PRIORITY + 2)   /* Orta   */
#define PRIO_UARTTX             (tskIDLE_PRIORITY + 1)   /* Düşük  */

/* ---- Görev yığınları (word) ---- */
#define STACK_TELEMETRY         256u
#define STACK_BUTTON            256u
#define STACK_UARTTX            384u

/* ---- Kuyruklar ---- */
#define BUTTON_QUEUE_LEN        8u      /* Buton: 8 olay               */
#define TX_QUEUE_LEN            16u     /* TX: 16 mesaj, FIFO          */
#define CMD_QUEUE_LEN           4u      /* PC komutları (yalnız RX)    */
#define REPLY_QUEUE_LEN         8u      /* Varyant B/C: öncelikli yanıt kuyruğu */

/* ---- UART ---- */
#define UART_BAUD               115200u /* 8N1                          */
#define MSG_LEN                 64u     /* Her TEL / BTN mesajı 64 bayt */
#define LINE_MAX                128u    /* LOG/CNT/INF satırları (ölçüm dışı) */
#define CMD_MAX                 16u

/* ---- Zamanlama ---- */
#define DEADLINE_US             20000u   /* R = t4 - t0 <= 20 ms        */
#define DEBOUNCE_US             30000u   /* 30 ms tekrar-kenar filtresi */
#define WARMUP_MS               5000u    /* 5 s ısınma                  */
#define TX_TIMEOUT_MS           1000u    /* TC bekleme / deney timeout'u */
#define CTL_LONG_PRESS_US       1000000u /* boşta uzun basış = START        */
#define AUTO_STOP_EVENTS        30u      /* varsayılan: bu kadar kabul edilen basıştan sonra deney biter */
#define INJ_MIN_MS              500u     /* EXTI enjeksiyonu: basışlar arası en az 0,5 s */
#define INJ_SPAN_MS             400u     /* + 0..400 ms rastgele (faz taraması)          */
#define EXTI_TEST_COUNT         100u     /* EXTI testi: yazılım tetiği -> ISR gecikmesi örnek sayısı */

/* ---- Olay kaydı ---- */
#define LOG_CAPACITY            128u     /* >= 64 olay; aşılırsa taşma sayacı */

#endif /* APP_CONFIG_H */
