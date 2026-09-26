/**
 * @file event_log.h
 * @brief Olay kimliğiyle indekslenen RAM kaydı (t0..t4 + durum) ve sayaçlar.
 *
 * Yazma sahipliği:
 *   t0 + kayıt açma ........ Buton ISR   (evlog_open)
 *   t1, t2 .................. ButtonTask
 *   t3, t4, durum ........... UartTxTask
 * Her alan tek bağlamdan yazılır; okuma (DUMP) yalnızca deney durduktan sonra.
 */
#ifndef EVENT_LOG_H
#define EVENT_LOG_H

#include <stdint.h>
#include <stdbool.h>

typedef enum {
    EV_PENDING = 0,
    EV_OK,          /* t4 kaydedildi (yanıt hattan çıktı)            */
    EV_BTN_DROP,    /* Buton kuyruğu doluydu; ButtonTask olayı almadı */
    EV_TX_DROP,     /* TX kuyruğu doluydu; yanıt gönderilemedi         */
    EV_TX_ERROR,    /* UART başlatma / format hatası                   */
    EV_TIMEOUT,     /* TC 1 s içinde gelmedi veya deney sonunda tamamlanmadı */
} ev_status_t;

enum { T0 = 0, T1, T2, T3, T4, T_COUNT };

typedef struct {
    uint32_t t[T_COUNT];
    uint8_t  have;      /* bit i => t[i] geçerli. Eksik zaman 0 DEĞİL, boş raporlanır. */
    uint8_t  status;    /* ev_status_t */
} ev_rec_t;

/* Sayaçlar: kayıp ve hatalar sonuçtan gizlenmez, DUMP ile raporlanır. */
typedef struct {
    volatile uint32_t accepted;       /* Kabul edilen basış (kimlik alan olay)   */
    volatile uint32_t bounce;         /* 30 ms içinde reddedilen kenar           */
    volatile uint32_t ignored;        /* Ölçüm dışı / ısınma sırasında basış     */
    volatile uint32_t btn_q_drop;     /* xQueueSendFromISR başarısız             */
    volatile uint32_t btn_tx_drop;    /* BTN yanıtı TX kuyruğuna giremedi        */
    volatile uint32_t tel_sent;       /* TX kuyruğuna giren TEL                  */
    volatile uint32_t tel_tx_drop;    /* TX kuyruğuna giremeyen TEL              */
    volatile uint32_t tx_error;       /* HAL başlatma hatası                     */
    volatile uint32_t tx_timeout;     /* TC 1 s içinde gelmedi                   */
    volatile uint32_t log_overflow;   /* LOG_CAPACITY aşıldı, kayıt tutulamadı   */
    volatile uint32_t fmt_error;      /* Mesaj 63 bayta sığmadı (kesilmedi)      */
} ev_counters_t;

extern ev_counters_t g_cnt;

void        evlog_reset(void);                          /* görev bağlamı, ölçüm dışı */
uint32_t    evlog_open_isr(uint32_t t0);                /* yeni kimlik döner (1..)   */
void        evlog_set(uint32_t id, int idx, uint32_t t);
void        evlog_status(uint32_t id, ev_status_t st);
void        evlog_finalize(void);                       /* PENDING -> TIMEOUT        */
bool        evlog_all_closed(void);                     /* PENDING olay kalmadı mı */
uint32_t    evlog_count(void);                          /* kaydedilen olay sayısı    */
bool        evlog_get(uint32_t id, ev_rec_t *out);
const char *evlog_status_str(uint8_t st);

#endif /* EVENT_LOG_H */
