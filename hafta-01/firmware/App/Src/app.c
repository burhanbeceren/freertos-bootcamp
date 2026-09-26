/**
 * @file app.c
 * @brief Kuyrukları ve 3 uygulama görevini oluşturur.
 */
#include "app.h"
#include "app_config.h"
#include "event_log.h"
#include "msg.h"

QueueHandle_t     g_button_q;
QueueHandle_t     g_tx_q;
QueueHandle_t     g_cmd_q;
TaskHandle_t      g_uarttx_task;
TaskHandle_t      g_tel_task;
volatile bool     g_started;
volatile uint32_t g_arm_at_us;

void app_init(void)
{
    evlog_reset();

    g_button_q = xQueueCreate(BUTTON_QUEUE_LEN, sizeof(button_event_t));
    g_tx_q     = xQueueCreate(TX_QUEUE_LEN, sizeof(tx_msg_t));
    g_cmd_q    = xQueueCreate(CMD_QUEUE_LEN, sizeof(cmd_t));
    configASSERT(g_button_q && g_tx_q && g_cmd_q);

    vQueueAddToRegistry(g_button_q, "buttonQ");
    vQueueAddToRegistry(g_tx_q, "txQ");

    BaseType_t ok = pdPASS;
    ok &= xTaskCreate(telemetry_task, "Telemetry", STACK_TELEMETRY, NULL, PRIO_TELEMETRY, &g_tel_task);
    ok &= xTaskCreate(button_task,    "Button",    STACK_BUTTON,    NULL, PRIO_BUTTON,    NULL);
    ok &= xTaskCreate(uarttx_task,    "UartTx",    STACK_UARTTX,    NULL, PRIO_UARTTX,    &g_uarttx_task);
    configASSERT(ok == pdPASS);

    button_init_irq();   /* Kuyruk hazır olduktan sonra EXTI açılır */
}
