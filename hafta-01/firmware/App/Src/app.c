/**
 * @file app.c
 * @brief Kuyrukları ve 3 uygulama görevini oluşturur.
 */
#include "app.h"
#include "app_config.h"
#include "event_log.h"
#include "msg.h"
#include <string.h>

QueueHandle_t     g_button_q;
QueueHandle_t     g_tx_q;
QueueHandle_t     g_reply_q;
QueueHandle_t     g_cmd_q;
TaskHandle_t      g_uarttx_task;
TaskHandle_t      g_tel_task;
TaskHandle_t      g_btn_task;
volatile variant_t g_variant = VAR_A;
volatile source_t  g_source = SRC_HW;
volatile uint32_t  g_target_events = AUTO_STOP_EVENTS;

__attribute__((section(".mailbox"))) volatile dbg_mailbox_t g_mailbox;

void app_apply_variant(variant_t v)
{
    UBaseType_t tel = PRIO_TELEMETRY, btn = PRIO_BUTTON, utx = PRIO_UARTTX;   /* A, B: 3 > 2 > 1 */
    if (v == VAR_C) {
        btn = tskIDLE_PRIORITY + 4;      /* yanıt CPU işini beklemez          */
        utx = tskIDLE_PRIORITY + 3;      /* UART görevi Telemetry'den önce    */
        tel = tskIDLE_PRIORITY + 2;
    }
    vTaskPrioritySet(g_tel_task, tel);
    vTaskPrioritySet(g_btn_task, btn);
    vTaskPrioritySet(g_uarttx_task, utx);
    g_variant = v;
}

const char *app_source_name(void)
{
    return (g_source == SRC_INJ) ? "INJ" : "HW";
}
volatile bool     g_started;
volatile uint32_t g_arm_at_us;
volatile bool     g_stop_pending;

void app_init(void)
{
    evlog_reset();

    g_button_q = xQueueCreate(BUTTON_QUEUE_LEN, sizeof(button_event_t));
    g_tx_q     = xQueueCreate(TX_QUEUE_LEN, sizeof(tx_msg_t));
    g_reply_q  = xQueueCreate(REPLY_QUEUE_LEN, sizeof(tx_msg_t));
    g_cmd_q    = xQueueCreate(CMD_QUEUE_LEN, sizeof(cmd_t));
    configASSERT(g_button_q && g_tx_q && g_reply_q && g_cmd_q);

    memset((void *)&g_mailbox, 0, sizeof g_mailbox);   /* NOLOAD: açılışta temizle */

    vQueueAddToRegistry(g_button_q, "buttonQ");
    vQueueAddToRegistry(g_tx_q, "txQ");

    BaseType_t ok = pdPASS;
    ok &= xTaskCreate(telemetry_task, "Telemetry", STACK_TELEMETRY, NULL, PRIO_TELEMETRY, &g_tel_task);
    ok &= xTaskCreate(button_task,    "Button",    STACK_BUTTON,    NULL, PRIO_BUTTON,    &g_btn_task);
    ok &= xTaskCreate(uarttx_task,    "UartTx",    STACK_UARTTX,    NULL, PRIO_UARTTX,    &g_uarttx_task);
    configASSERT(ok == pdPASS);

    button_init_irq();          /* Kuyruk hazır olduktan sonra EXTI açılır */
    control_button_init_irq();
    inject_init();
}
