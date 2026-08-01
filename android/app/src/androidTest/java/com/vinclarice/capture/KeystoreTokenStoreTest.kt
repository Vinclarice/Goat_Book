package com.vinclarice.capture

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * The encryption path, which has no JVM implementation to test against --
 * `AndroidKeyStore` exists only on a device or emulator. These compile in
 * CI and run at M4's device pilot.
 *
 * Everything around the cipher is already covered by JVM tests:
 * TokenEnvelopeTest for the framing, ConnectorTest for what connecting
 * means. What is left here is genuinely the part that needs hardware.
 */
@RunWith(AndroidJUnit4::class)
class KeystoreTokenStoreTest {

    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private val alias = "clarice_test_token"
    // Its own file, not the app's. See KeystoreTokenStore's comment:
    // sharing it once cost a live token off a real phone.
    private val prefsName = "clarice_test_secret"

    private fun store() = KeystoreTokenStore(context, alias = alias, prefsName = prefsName)

    @Before
    fun startClean() {
        store().clear()
    }

    @Test
    fun these_tests_never_touch_the_real_app_storage() {
        // Written after these tests deleted a live token off a real phone.
        // The alias was parameterised and the preference file was not, so
        // every run wrote to the app's own file with a key the app could
        // not decrypt -- and its owner was sent back to Connect.
        //
        // Isolating one half of the storage is isolating neither.
        val real = context.getSharedPreferences(
            "clarice_capture_secret",
            android.content.Context.MODE_PRIVATE,
        )
        val before = real.getString("token", null)

        store().save("tok_from_a_test")
        store().clear()

        assertEquals(before, real.getString("token", null))
        assertNotEquals("clarice_capture_secret", prefsName)
    }

    @Test
    fun a_saved_token_reads_back_unchanged() {
        val token = "tok_" + "z9x8".repeat(10)

        store().save(token)

        assertEquals(token, store().read())
    }

    @Test
    fun nothing_is_stored_before_anything_is_saved() {
        assertNull(store().read())
    }

    @Test
    fun a_second_save_replaces_the_first() {
        store().save("tok_first")
        store().save("tok_second")

        assertEquals("tok_second", store().read())
    }

    @Test
    fun clearing_forgets_the_token() {
        store().save("tok_value")

        store().clear()

        assertNull(store().read())
    }

    @Test
    fun the_token_is_not_written_to_disk_in_the_clear() {
        // The whole point. If this ever fails, the file is readable by
        // anything that gets at the app's data directory.
        val token = "tok_plaintext_probe"
        store().save(token)

        val raw = context
            .getSharedPreferences(prefsName, android.content.Context.MODE_PRIVATE)
            .getString("token", "")

        assertNotEquals("", raw)
        // assertFalse, not Kotlin's assert(): that one compiles to nothing
        // unless assertions are enabled at runtime, so the check would
        // silently never run.
        assertFalse("the token was stored in the clear", raw!!.contains(token))
    }

    @Test
    fun a_corrupted_value_reads_as_no_token_rather_than_throwing() {
        // What a restore onto a new device looks like: ciphertext present,
        // key gone or unusable. It has to behave like "not connected", not
        // like a crash, because the recovery is the same either way -- ask
        // for the token again.
        store().save("tok_value")
        context
            .getSharedPreferences(prefsName, android.content.Context.MODE_PRIVATE)
            .edit()
            .putString("token", "bm90:cmVhbGx5")
            .commit()

        assertNull(store().read())
    }

    @Test
    fun a_corrupted_value_does_not_poison_the_next_connection() {
        store().save("tok_value")
        context
            .getSharedPreferences(prefsName, android.content.Context.MODE_PRIVATE)
            .edit()
            .putString("token", "garbage-without-a-separator")
            .commit()

        assertNull(store().read())
        store().save("tok_fresh")

        assertEquals("tok_fresh", store().read())
    }
}
