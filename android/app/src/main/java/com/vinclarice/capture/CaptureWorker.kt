package com.vinclarice.capture

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit

/**
 * Asking for the queue to be delivered.
 *
 * An interface so the view model can be tested on the JVM without
 * WorkManager, and because everything the app needs to say is "there is
 * something to send" -- when and how are the system's business.
 */
fun interface DeliveryScheduler {
    fun schedule()
}

/**
 * Drains the queue in the background, under the system's constraints rather
 * than the app's optimism.
 *
 * Thin on purpose: every decision it could get wrong lives in [QueueDrainer],
 * which has tests. What is left here is translating a [DrainReport] into the
 * two words WorkManager understands.
 */
class CaptureWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val report = QueueDrainer(
            api = OkHttpClariceApi(baseUrl = BuildConfig.CLARICE_BASE_URL),
            store = KeystoreTokenStore(applicationContext),
            queue = CaptureQueue(EncryptedQueueStorage(applicationContext)),
        ).drain()

        // retry() rather than failure(): failure is terminal, and nothing
        // here is ever terminal while a capture is still waiting. A stalled
        // or rejected item does not count as waiting, which is what stops
        // this rescheduling forever over something no retry can fix.
        return if (report.finished) Result.success() else Result.retry()
    }

    companion object : DeliveryScheduler {

        /**
         * Not usable as a scheduler until [prepare] has been given a
         * context. `Companion` is a singleton with no application of its
         * own, and passing one in beats holding a static Context.
         */
        private var appContext: Context? = null

        fun prepare(context: Context): DeliveryScheduler {
            appContext = context.applicationContext
            return this
        }

        override fun schedule() {
            val context = appContext ?: return
            val request = OneTimeWorkRequestBuilder<CaptureWorker>()
                .setConstraints(
                    Constraints.Builder()
                        // The one thing worth waiting for. Without it the
                        // worker wakes in airplane mode, fails, and spends
                        // an attempt to learn what the system already knew.
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .build()
                )
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build()

            // KEEP, emphatically not REPLACE. Replacing would restart the
            // backoff every time somebody captured another thought, so a
            // person typing steadily through an outage would push their own
            // queue's next attempt further away with every capture.
            WorkManager.getInstance(context)
                .enqueueUniqueWork(WORK_NAME, ExistingWorkPolicy.KEEP, request)
        }

        private const val WORK_NAME = "clarice-capture-delivery"
    }
}
