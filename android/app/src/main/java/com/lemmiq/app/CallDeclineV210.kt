package com.lemmiq.app

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.util.concurrent.ConcurrentHashMap

/**
 * LEMMIQ V2.10 call-decline guard.
 *
 * This helper is deliberately independent from Retrofit/LiveKit classes so it can be added
 * to the existing V2.9 project without replacing its call stack. The Activity/Service passes
 * the existing backend-decline and cleanup callbacks into decline().
 */
object CallDeclineV210 {
    private val terminalCalls = ConcurrentHashMap.newKeySet<String>()
    private val locks = ConcurrentHashMap<String, Mutex>()

    enum class State {
        IDLE, CALLING, RINGING, CONNECTING, CONNECTED, DECLINED, ENDED, MISSED, FAILED
    }

    private fun isTerminal(state: State): Boolean = state in setOf(
        State.DECLINED, State.ENDED, State.MISSED, State.FAILED
    )

    /** Mark a call as terminal locally as soon as decline begins. */
    fun markDeclined(callId: String?) {
        val id = callId?.trim().orEmpty()
        if (id.isNotEmpty()) terminalCalls += id
    }

    fun markEnded(callId: String?) {
        val id = callId?.trim().orEmpty()
        if (id.isNotEmpty()) terminalCalls += id
    }

    fun clear(callId: String?) {
        val id = callId?.trim().orEmpty()
        if (id.isNotEmpty()) {
            terminalCalls.remove(id)
            locks.remove(id)
        }
    }

    fun isTerminal(callId: String?): Boolean {
        val id = callId?.trim().orEmpty()
        return id.isNotEmpty() && id in terminalCalls
    }

    /**
     * Use before processing answer/connect/ringing callbacks.
     * A declined/ended call is never allowed to become active again.
     */
    fun canTransition(callId: String?, from: State, to: State): Boolean {
        if (isTerminal(callId) && !isTerminal(to)) return false
        if (isTerminal(from) && !isTerminal(to)) return false
        return true
    }

    /**
     * Idempotent decline operation. Run this from lifecycleScope / serviceScope.
     *
     * Sequence is intentionally:
     * 1) mark local terminal immediately (blocks race-to-connect)
     * 2) stop local ringing/audio ASAP
     * 3) tell backend/caller
     * 4) disconnect room/tracks/listeners/services
     * 5) close the incoming-call UI
     *
     * Cleanup continues even if the backend call fails.
     */
    suspend fun decline(
        callId: String,
        stopRingingImmediately: () -> Unit,
        backendDecline: suspend (String) -> Unit,
        disconnectRoomAndTracks: suspend () -> Unit,
        releaseAudioFocus: () -> Unit,
        cancelTimersAndListeners: () -> Unit,
        stopCallForegroundService: () -> Unit,
        closeIncomingCallUi: () -> Unit,
        onBackendFailure: (Throwable) -> Unit = {}
    ) {
        val id = callId.trim()
        if (id.isEmpty()) {
            stopRingingImmediately()
            releaseAudioFocus()
            cancelTimersAndListeners()
            stopCallForegroundService()
            closeIncomingCallUi()
            return
        }

        val mutex = locks.getOrPut(id) { Mutex() }
        mutex.withLock {
            // A second Decline tap/event is safe and only performs local cleanup.
            val firstDecline = terminalCalls.add(id)
            stopRingingImmediately()

            if (firstDecline) {
                try {
                    backendDecline(id)
                } catch (t: Throwable) {
                    onBackendFailure(t)
                }
            }

            try {
                disconnectRoomAndTracks()
            } catch (_: Throwable) {
                // Never leave the incoming UI/ringer alive because LiveKit cleanup threw.
            }

            try { releaseAudioFocus() } catch (_: Throwable) {}
            try { cancelTimersAndListeners() } catch (_: Throwable) {}
            try { stopCallForegroundService() } catch (_: Throwable) {}
            try { closeIncomingCallUi() } catch (_: Throwable) {}
        }
    }
}
