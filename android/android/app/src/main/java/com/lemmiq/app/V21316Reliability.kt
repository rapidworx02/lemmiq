package com.lemmiq.app

/**
 * V2.13.16 — WebSocket ticket safety and bounded reconnect intervals.
 * Tickets are ephemeral and must never be written to application logs or URLs.
 */
internal object V21316Reliability {
    fun websocketProtocols(ticket: String): String {
        require(ticket.length in 30..128 && ticket.all { it.isLetterOrDigit() || it == '_' || it == '-' }) {
            "Invalid WebSocket ticket"
        }
        return "lemmiq.v1, ticket.$ticket"
    }

    fun reconnectDelayMs(attempt: Int): Long {
        val n = attempt.coerceIn(1, 6)
        return (1500L shl (n - 1)).coerceAtMost(30000L)
    }
}
