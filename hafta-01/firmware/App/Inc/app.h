/**
 * @file app.h
 * @brief Uygulama katmanı giriş noktası ve görevler arası paylaşılan tutamaklar.
 *
 * 3 uygulama görevi: TelemetryTask (3), ButtonTask (2), UartTxTask (1).
 * Idle görevi bu sayıya dahil değildir. ISR bir görev değildir.
 */
#ifndef APP_H
#define APP_H

#include <stdint.h>
#include <stdbool.h>
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "stm32f4xx_hal.h"

/* Buton ISR -> ButtonTask */
typedef struct {
    uint32_t id;
    uint32_t t0_us;
} button_event_t;

/* PC -> UartTxTask (RX ISR ile toplanan satır) */
typedef struct {
    char text[16];
} cmd_t;

extern QueueHandle_t      g_button_q;   /* 8 olay  */
extern QueueHandle_t      g_tx_q;       /* 16 mesaj */
extern QueueHandle_t      g_reply_q;    /* Varyant B/C: BTN yanıtları için öncelikli kuyruk */
extern QueueHandle_t      g_cmd_q;
extern TaskHandle_t       g_uarttx_task;
extern TaskHandle_t       g_tel_task;
extern TaskHandle_t       g_btn_task;

/*
 * Gecikme azaltma varyantları (yalnızca ölçüm durmuşken değiştirilir):
 *  A  Görev standardı: tek TX FIFO, öncelikler Telemetry 3 > Button 2 > UartTx 1
 *  B  A + öncelikli yanıt kuyruğu: BTN, TEL birikmesinin arkasında beklemez
 *  C  B + görev önceliği Button > UartTx > Telemetry: CPU işini beklemez,
 *     UART görevi aç kalmaz
 */
typedef enum { VAR_A = 'A', VAR_B = 'B', VAR_C = 'C' } variant_t;
/* Uyarım kaynağı: fiziksel buton (HW) veya donanım zamanlayıcısıyla EXTI enjeksiyonu (INJ) */
typedef enum { SRC_HW = 0, SRC_INJ = 1 } source_t;

extern volatile variant_t g_variant;
extern volatile source_t  g_source;
extern volatile uint32_t  g_target_events;   /* otomatik durdurma için olay sayısı */

/* PC -> kart posta kutusu (0x20000000). ST-LINK ile yazılır: önce text, sonra seq. */
typedef struct {
    char              text[16];
    volatile uint32_t seq;
} dbg_mailbox_t;
extern volatile dbg_mailbox_t g_mailbox;

void app_apply_variant(variant_t v);         /* öncelikleri ayarlar */
const char *app_source_name(void);
extern UART_HandleTypeDef huart2;

/* Ölçüm durumu (UartTxTask yazar, ISR/görevler okur) */
extern volatile bool      g_started;      /* START alındı            */
extern volatile uint32_t  g_arm_at_us;    /* bu andan sonra basış kabul */
extern volatile bool      g_stop_pending; /* AUTO_STOP_EVENTS doldu, kapanış bekleniyor */

void app_init(void);                      /* scheduler öncesi çağrılır */

/* Görev gövdeleri */
void telemetry_task(void *arg);
void button_task(void *arg);
void uarttx_task(void *arg);

/* TelemetryTask kontrolü (UartTxTask çağırır) */
void telemetry_start(void);
void telemetry_stop(void);
void telemetry_stats(uint32_t *per_min, uint32_t *per_max,
                     uint32_t *work_min, uint32_t *work_max);

void button_init_irq(void);

/* EXTI enjeksiyonu ve EXTI testi (inject.c) */
void     inject_init(void);
void     inject_start(void);                 /* START: ısınmadan sonra ilk basış */
void     inject_stop(void);
bool     inject_take_pending(void);          /* EXTI0 ISR: bu kenar enjekte mi? */
bool     exti_test_hook(void);               /* EXTI0 ISR: test kenarıysa true */
void     exti_test_run(uint32_t n, uint32_t *mn, uint32_t *mean, uint32_t *mx);
void control_button_init_irq(void);   /* PE7: deney kontrol butonu */

#endif /* APP_H */
