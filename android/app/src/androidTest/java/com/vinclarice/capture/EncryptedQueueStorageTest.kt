package com.vinclarice.capture

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * The queue's encryption path, which has no JVM implementation to test
 * against -- `AndroidKeyStore` exists only on a device.
 *
 * What the queue *means* is covered by CaptureQueueTest, and its
 * serialization by QueueDocumentTest. What is left here is the part that
 * genuinely needs hardware.
 */
@RunWith(AndroidJUnit4::class)
class EncryptedQueueStorageTest {

    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private val alias = "clarice_test_queue"
    private val prefsName = "clarice_test_queue_store"

    private fun storage() = EncryptedQueueStorage(context, alias = alias, prefsName = prefsName)

    private val thought = PendingCapture(
        key = "11111111-2222-3333-4444-555555555555",
        text = "a thought with \"quotes\" and\na newline",
        createdAt = 1_700_000_000_000,
        attempts = 2,
    )

    @Before
    fun startClean() {
        storage().save(emptyList())
    }

    @Test
    fun these_tests_never_touch_the_real_app_storage() {
        // The lesson from KeystoreTokenStoreTest, applied before it can be
        // learned twice: parameterising the alias but not the file name once
        // deleted a live token off a real phone.
        val real = context.getSharedPreferences(
            "clarice_capture_queue_store",
            android.content.Context.MODE_PRIVATE,
        )
        val before = real.getString("queue", null)

        storage().save(listOf(thought))

        assertEquals(before, real.getString("queue", null))
        assertNotEquals("clarice_capture_queue_store", prefsName)
    }

    @Test
    fun a_saved_queue_reads_back_unchanged() {
        storage().save(listOf(thought))

        assertEquals(listOf(thought), storage().load())
    }

    @Test
    fun an_empty_queue_is_not_an_error() {
        assertTrue(storage().load().isEmpty())
    }

    @Test
    fun the_queue_survives_a_new_storage_object_over_the_same_file() {
        // Standing in for process death, which is the whole reason this
        // class exists.
        storage().save(listOf(thought))

        assertEquals(listOf(thought), EncryptedQueueStorage(context, alias, prefsName).load())
    }

    @Test
    fun captured_text_is_not_written_to_disk_in_the_clear() {
        // The whole point. Capture text is somebody's unfiltered thinking.
        storage().save(listOf(thought))

        val raw = context
            .getSharedPreferences(prefsName, android.content.Context.MODE_PRIVATE)
            .getString("queue", "")

        assertNotEquals("", raw)
        // assertFalse, not Kotlin's assert(): that one compiles to nothing
        // unless assertions are enabled at runtime, so the check would
        // silently never run.
        assertFalse("capture text was stored in the clear", raw!!.contains("a thought"))
        assertFalse("the idempotency key was stored in the clear", raw.contains(thought.key))
    }

    @Test
    fun a_corrupted_queue_reads_as_empty_rather_than_throwing() {
        storage().save(listOf(thought))
        context
            .getSharedPreferences(prefsName, android.content.Context.MODE_PRIVATE)
            .edit()
            .putString("queue", "bm90:cmVhbGx5")
            .commit()

        assertTrue(storage().load().isEmpty())
    }

    @Test
    fun a_corrupted_queue_does_not_poison_the_next_capture() {
        storage().save(listOf(thought))
        context
            .getSharedPreferences(prefsName, android.content.Context.MODE_PRIVATE)
            .edit()
            .putString("queue", "garbage-without-a-separator")
            .commit()

        assertTrue(storage().load().isEmpty())
        storage().save(listOf(thought))

        assertEquals(listOf(thought), storage().load())
    }

    @Test
    fun the_queue_and_the_token_do_not_share_a_key() {
        // Disconnecting deletes the token's key. If the queue rode on it,
        // every unsent thought would vanish at the exact moment somebody was
        // told their token had stopped working.
        val tokens = KeystoreTokenStore(context, "clarice_test_shared_token", "clarice_test_shared_prefs")
        tokens.save("tok_value")
        storage().save(listOf(thought))

        tokens.clear()

        assertEquals(listOf(thought), storage().load())
    }
}
