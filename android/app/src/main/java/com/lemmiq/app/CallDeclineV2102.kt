package com.lemmiq.app

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.util.concurrent.ConcurrentHashMap

/**
 * V2.10.2 retains the V2.10 terminal decline guard.
 * Wire this into the actual incoming-call Decline action.
 */
object CallDeclineV2102 {
    private val terminalCalls = ConcurrentHashMap.newKeySet<String>()
    private val locks = ConcurrentHashMap<String, Mutex>()

    enum class State {
        IDLE, CALLING, RINGING, CONNECTING, CONNECTED, DECLINED, ENDED, MISSED, FAILED
    }

    private fun isTerminalState(state: State) = state in setOf(
        State.DECLINED, State.ENDED, State.MISSED, State.FAILED
    )

    fun isTerminal(callId: String?): Boolean {
        val id = callId?.trim().orEmpty()
        return id.isNotEmpty() && id in terminalCalls
    }

    fun canTransition(callId: String?, from: State, to: State): Boolean {
        if (isTerminal(callId) && !isTerminalState(to)) return false
        if (isTerminalState(from) && !isTerminalState(to)) return false
        return true
    }

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
            val firstDecline = terminalCalls.add(id)
            stopRingingImmediately()

            if (firstDecline) {
                try { backendDecline(id) } catch (t: Throwable) { onBackendFailure(t) }
            }

            try { disconnectRoomAndTracks() } catch (_: Throwable) {}
            try { releaseAudioFocus() } catch (_: Throwable) {}
            try { cancelTimersAndListeners() } catch (_: Throwable) {}
            try { stopCallForegroundService() } catch (_: Throwable) {}
            try { closeIncomingCallUi() } catch (_: Throwable) {}
        }
    }
}
