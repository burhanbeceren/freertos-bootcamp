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
extern QueueHandle_t      g_cmd_q;
extern TaskHandle_t       g_uarttx_task;
extern TaskHandle_t       g_tel_task;
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
void control_button_init_irq(void);   /* PE7: deney kontrol butonu */

#endif /* APP_H */
