/**
 * @file uart_tx.c
 * @brief UartTxTask — düşük öncelik. UART'ın TEK sahibi.
 *
 *  - TX FIFO kuyruğunu tüketir; t3'ü kaydedip DMA gönderimini başlatır.
 *  - Gönderim tamamlanana (USART TC) kadar görev bloklanır; t4 TC kesmesinde alınır.
 *  - Başlatma başarısızsa olay tx_error, TC 1 s içinde gelmezse timeout olur.
 *  - PC komutlarını (RX) da bu görev işler; hatta başka hiçbir bağlam yazmaz.
 */
#include "app.h"
#include "main.h"
#include "app_config.h"
#include "event_log.h"
#include "msg.h"
#include "scenario.h"
#include "timebase.h"
#include "work.h"
#include <string.h>

#ifndef FW_GIT_REV
#define FW_GIT_REV "unknown"
#endif
#ifndef FW_BUILD_PROFILE
#define FW_BUILD_PROFILE "unknown"
#endif

typedef enum { TX_OK = 0, TX_START_FAIL, TX_TIMEOUT } tx_result_t;

extern DMA_HandleTypeDef hdma_usart2_tx;

static QueueSetHandle_t  s_set;
static tx_msg_t          s_cur;              /* Aktarım sonuna kadar yaşayan tampon */
static char              s_line[LINE_MAX];   /* Ölçüm dışı satırlar için           */
static volatile uint32_t s_tc_us;            /* t4: TC ISR'da yazılır              */

/* RX satır birleştirme (yalnız USART2 ISR bağlamı) */
static char     s_rx_buf[CMD_MAX];
static uint32_t s_rx_len;
static bool     s_rx_overflow;

/* ------------------------------------------------------------------------- */
/* Kesmeler                                                                  */
/* ------------------------------------------------------------------------- */

void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{
    /* HAL, DMA modunda da bu callback'i USART TC (son stop biti) ile çağırır;
       "DMA bitti" anında değil. */
    if (huart->Instance == USART2) {
        s_tc_us = timer_us();                           /* t4 */
        BaseType_t wake = pdFALSE;
        vTaskNotifyGiveFromISR(g_uarttx_task, &wake);
        portYIELD_FROM_ISR(wake);
    }
}

static void rx_byte_isr(uint8_t b)
{
    if (b == '\r') {
        return;
    }
    if (b == '\n') {
        if (s_rx_len > 0u && !s_rx_overflow) {
            cmd_t c;
            memcpy(c.text, s_rx_buf, s_rx_len);
            c.text[s_rx_len] = '\0';
            BaseType_t wake = pdFALSE;
            (void)xQueueSendFromISR(g_cmd_q, &c, &wake);
            portYIELD_FROM_ISR(wake);
        }
        s_rx_len = 0;
        s_rx_overflow = false;
        return;
    }
    if (s_rx_len < (CMD_MAX - 1u)) {
        s_rx_buf[s_rx_len++] = (char)b;
    } else {
        s_rx_overflow = true;                           /* satır atılır, kesilmez */
    }
}

void USART2_IRQHandler(void)
{
    /* RX HAL'e verilmez: HAL TX kilidiyle yarışmamak için bayt burada okunur.
       SR ardından DR okuması RXNE/ORE/FE/NE bayraklarını temizler. */
    const uint32_t sr = USART2->SR;
    if ((sr & (USART_SR_RXNE | USART_SR_ORE | USART_SR_FE | USART_SR_NE)) != 0u) {
        const uint8_t b = (uint8_t)USART2->DR;
        if ((sr & USART_SR_RXNE) != 0u && (sr & (USART_SR_FE | USART_SR_NE)) == 0u) {
            rx_byte_isr(b);
        }
    }
    HAL_UART_IRQHandler(&huart2);                       /* TC -> TxCpltCallback */
}

void DMA1_Stream6_IRQHandler(void)
{
    HAL_DMA_IRQHandler(&hdma_usart2_tx);
}

/* ------------------------------------------------------------------------- */
/* Gönderim                                                                  */
/* ------------------------------------------------------------------------- */

static tx_result_t uart_send_wait(const char *buf, uint16_t len, uint32_t *t3, uint32_t *t4)
{
    (void)ulTaskNotifyTake(pdTRUE, 0);                  /* eski bildirimi temizle */

    *t3 = timer_us();                                   /* t3: başlatmadan hemen önce */
    if (HAL_UART_Transmit_DMA(&huart2, (uint8_t *)buf, len) != HAL_OK) {
        g_cnt.tx_error++;
        return TX_START_FAIL;
    }
    if (ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(TX_TIMEOUT_MS)) == 0u) {
        (void)HAL_UART_AbortTransmit(&huart2);          /* sonsuz bekleme yok */
        g_cnt.tx_timeout++;
        return TX_TIMEOUT;
    }
    *t4 = s_tc_us;
    return TX_OK;
}

static void send_queued(const tx_msg_t *m)
{
    uint32_t t3 = 0, t4 = 0;
    const tx_result_t r = uart_send_wait(m->data, MSG_LEN, &t3, &t4);

    if (m->kind != MSG_BTN) {
        return;
    }
    /* Kayıt doğru olay kimliğiyle kapatılır. */
    evlog_set(m->event_id, T3, t3);
    switch (r) {
    case TX_OK:
        evlog_set(m->event_id, T4, t4);
        evlog_status(m->event_id, EV_OK);
        break;
    case TX_START_FAIL:
        evlog_status(m->event_id, EV_TX_ERROR);
        break;
    default:
        evlog_status(m->event_id, EV_TIMEOUT);
        break;
    }
}

/* Ölçüm dışı (komut yanıtı / döküm) satırı gönderir. */
static void send_line(sb_t *sb)
{
    uint32_t t3, t4;
    if (!msg_seal_line(sb)) {
        g_cnt.fmt_error++;
        return;
    }
    (void)uart_send_wait(sb->buf, (uint16_t)sb->len, &t3, &t4);
}

static void reply2(const char *a, const char *b)
{
    sb_t sb;
    sb_init(&sb, s_line, sizeof s_line);
    sb_str(&sb, a);
    if (b != NULL) {
        sb_char(&sb, ',');
        sb_str(&sb, b);
    }
    send_line(&sb);
}

static void kv(const char *tag, const char *key, uint32_t val)
{
    sb_t sb;
    sb_init(&sb, s_line, sizeof s_line);
    sb_str(&sb, tag);
    sb_char(&sb, ',');
    sb_str(&sb, key);
    sb_char(&sb, ',');
    sb_u32(&sb, val);
    send_line(&sb);
}

static void kvs(const char *tag, const char *key, const char *val)
{
    sb_t sb;
    sb_init(&sb, s_line, sizeof s_line);
    sb_str(&sb, tag);
    sb_char(&sb, ',');
    sb_str(&sb, key);
    sb_char(&sb, ',');
    sb_str(&sb, val);
    send_line(&sb);
}

/* ------------------------------------------------------------------------- */
/* Komutlar                                                                  */
/* ------------------------------------------------------------------------- */

static void drain_tx_queue(void)
{
    while (xQueueReceive(g_tx_q, &s_cur, 0) == pdPASS) {
        send_queued(&s_cur);
    }
}

static void stop_measurement(void)
{
    g_started = false;           /* yeni basış kabul edilmez           */
    telemetry_stop();            /* TelemetryTask bir sonraki uyanışta bloklanır */
    drain_tx_queue();            /* bekleyen TX'i tamamla / timeout kaydet */
    evlog_finalize();            /* tamamlanmayanlar -> timeout         */
    HAL_GPIO_WritePin(LED_PORT, LED_ORANGE_PIN, GPIO_PIN_RESET);
}

static void cmd_info(void)
{
    kvs("INF", "fw", APP_FW_VERSION);
    kvs("INF", "git", FW_GIT_REV);
    kvs("INF", "build", FW_BUILD_PROFILE);
    kv ("INF", "sysclk_hz", HAL_RCC_GetSysClockFreq());
    kv ("INF", "tick_hz", configTICK_RATE_HZ);
    kv ("INF", "timer_hz", 1000000u);
    kv ("INF", "baud", UART_BAUD);
    kv ("INF", "msg_len", MSG_LEN);
    kv ("INF", "btn_q", BUTTON_QUEUE_LEN);
    kv ("INF", "tx_q", TX_QUEUE_LEN);
    kv ("INF", "deadline_us", DEADLINE_US);
    kv ("INF", "debounce_us", DEBOUNCE_US);
    kv ("INF", "warmup_ms", WARMUP_MS);
    kv ("INF", "log_capacity", LOG_CAPACITY);
    kv ("INF", "iters_per_ms", work_iters_per_ms());
    kvs("INF", "scenario", scenario_current()->name);
    reply2("ACK", "INFO");
}

static void cmd_dump(void)
{
    const char *scn = scenario_current()->name;
    const uint32_t n = evlog_count();
    ev_rec_t r;

    for (uint32_t id = 1; id <= n; id++) {
        if (!evlog_get(id, &r)) {
            continue;
        }
        sb_t sb;
        sb_init(&sb, s_line, sizeof s_line);
        sb_str(&sb, "LOG,");
        sb_str(&sb, scn);
        sb_char(&sb, ',');
        sb_u32(&sb, id);
        for (int i = 0; i < T_COUNT; i++) {
            sb_char(&sb, ',');
            if ((r.have & (1u << i)) != 0u) {
                sb_u32(&sb, r.t[i]);          /* eksik zaman boş bırakılır, 0 yazılmaz */
            }
        }
        sb_char(&sb, ',');
        sb_str(&sb, evlog_status_str(r.status));
        send_line(&sb);
    }

    uint32_t pmin, pmax, wmin, wmax;
    telemetry_stats(&pmin, &pmax, &wmin, &wmax);

    kv("CNT", "accepted",        g_cnt.accepted);
    kv("CNT", "logged",          n);
    kv("CNT", "bounce_rejected", g_cnt.bounce);
    kv("CNT", "ignored",         g_cnt.ignored);
    kv("CNT", "btn_q_drop",      g_cnt.btn_q_drop);
    kv("CNT", "btn_tx_drop",     g_cnt.btn_tx_drop);
    kv("CNT", "tel_sent",        g_cnt.tel_sent);
    kv("CNT", "tel_tx_drop",     g_cnt.tel_tx_drop);
    kv("CNT", "tx_error",        g_cnt.tx_error);
    kv("CNT", "tx_timeout",      g_cnt.tx_timeout);
    kv("CNT", "log_overflow",    g_cnt.log_overflow);
    kv("CNT", "fmt_error",       g_cnt.fmt_error);
    kv("CNT", "tel_period_min_us", pmin);
    kv("CNT", "tel_period_max_us", pmax);
    kv("CNT", "work_min_us",     wmin);
    kv("CNT", "work_max_us",     wmax);
    kv("CNT", "hwm_telemetry_w", uxTaskGetStackHighWaterMark(g_tel_task));
    kv("CNT", "hwm_uarttx_w",    uxTaskGetStackHighWaterMark(NULL));
    kv("CNT", "heap_free_min_b", (uint32_t)xPortGetMinimumEverFreeHeapSize());
    kvs("END", "DUMP", scn);
}

static void handle_cmd(const cmd_t *c)
{
    const char *t = c->text;

    if (strcmp(t, "PING") == 0) {
        reply2("ACK", "PING");
    } else if (strcmp(t, "INFO") == 0) {
        cmd_info();
    } else if (strncmp(t, "SCN,", 4) == 0) {
        const scenario_t *s = scenario_find(t + 4);
        if (s == NULL) {
            reply2("NAK", "SCN,unknown");
        } else if (g_started) {
            reply2("NAK", "SCN,running");
        } else {
            drain_tx_queue();                 /* önceki TX'i bitir     */
            evlog_reset();                    /* kayıt + sayaç sıfırla */
            scenario_set(s);
            reply2("ACK,SCN", s->name);
        }
    } else if (strcmp(t, "START") == 0) {
        if (g_started) {
            reply2("NAK", "START,running");
        } else {
            drain_tx_queue();
            evlog_reset();
            g_arm_at_us = timer_us() + (WARMUP_MS * 1000u);
            g_started = true;
            telemetry_start();
            HAL_GPIO_WritePin(LED_PORT, LED_ORANGE_PIN, GPIO_PIN_SET);
            reply2("ACK,START", scenario_current()->name);
        }
    } else if (strcmp(t, "STOP") == 0) {
        stop_measurement();
        reply2("ACK,STOP", scenario_current()->name);
    } else if (strcmp(t, "DUMP") == 0) {
        if (g_started) {
            reply2("NAK", "DUMP,running");   /* önce STOP: telemetri durmadan döküm yok */
        } else {
            cmd_dump();
        }
    } else {
        reply2("NAK", "unknown");
    }
}

/* ------------------------------------------------------------------------- */
/* Görev                                                                     */
/* ------------------------------------------------------------------------- */

void uarttx_task(void *arg)
{
    (void)arg;

    /* STOP sırasında doğrudan boşaltılan kuyruğun bayat tutamaçları için 2x pay */
    s_set = xQueueCreateSet((2u * TX_QUEUE_LEN) + CMD_QUEUE_LEN);
    configASSERT(s_set != NULL);
    (void)xQueueAddToSet(g_tx_q, s_set);
    (void)xQueueAddToSet(g_cmd_q, s_set);

    /* RX kesmesini aç (HAL RX API'si kullanılmıyor) */
    __HAL_UART_ENABLE_IT(&huart2, UART_IT_RXNE);

    reply2("BOOT", APP_FW_VERSION);
    cmd_info();

    for (;;) {
        QueueSetMemberHandle_t h = xQueueSelectFromSet(s_set, portMAX_DELAY);
        if (h == g_tx_q) {
            /* STOP sırasında doğrudan boşaltılmış olabilir: boşsa atla */
            if (xQueueReceive(g_tx_q, &s_cur, 0) == pdPASS) {
                send_queued(&s_cur);
            }
        } else if (h == g_cmd_q) {
            cmd_t c;
            if (xQueueReceive(g_cmd_q, &c, 0) == pdPASS) {
                handle_cmd(&c);
            }
        }
    }
}
