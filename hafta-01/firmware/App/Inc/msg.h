/**
 * @file msg.h
 * @brief Sabit 64 baytlık TEL/BTN mesajları ve heap kullanmayan metin oluşturucu.
 *
 * Kural: ASCII metin boşlukla 63 bayta tamamlanır, 64. bayt LF'dir.
 * Metin 63 baytı aşarsa mesaj KESİLMEZ; oluşturma başarısız döner.
 */
#ifndef MSG_H
#define MSG_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "app_config.h"

typedef enum { MSG_TEL = 1, MSG_BTN = 2 } msg_kind_t;

/* TX kuyruğu elemanı. Kuyruk kopyalayarak taşır: yerel tampon ömrüne güvenilmez. */
typedef struct {
    uint8_t  kind;              /* msg_kind_t                     */
    uint8_t  reserved[3];
    uint32_t event_id;          /* BTN için olay kimliği, TEL için sıra no */
    char     data[MSG_LEN];     /* Hatta çıkan 64 bayt            */
} tx_msg_t;

/* Basit string builder */
typedef struct {
    char   *buf;
    size_t  cap;
    size_t  len;
    bool    overflow;
} sb_t;

void sb_init(sb_t *sb, char *buf, size_t cap);
void sb_str(sb_t *sb, const char *s);
void sb_u32(sb_t *sb, uint32_t v);
void sb_char(sb_t *sb, char c);

/* sb içeriğini 63 bayta boşlukla tamamlar + LF. Sığmazsa false. */
bool msg_seal_fixed(sb_t *sb);
/* Değişken uzunluklu satır: sonuna LF ekler. Sığmazsa false. */
bool msg_seal_line(sb_t *sb);

#endif /* MSG_H */
