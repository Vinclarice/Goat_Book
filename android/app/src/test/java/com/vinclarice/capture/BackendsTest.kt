package com.vinclarice.capture

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Which server each concern talks to, and with which credential.
 *
 * This client now faces two servers rather than one: capture belongs to
 * Second Mind, while Today and Agenda stay with Clarice, which is the only
 * one that has tasks. See Second Mind's docs/android-two-backends.md.
 *
 * A pure function over two configured URLs, so the decision is testable here
 * rather than only on a phone with two accounts.
 */
class BackendsTest {

    private val clarice = "https://vinclarice.com/"
    private val secondMind = "https://mind.example/"

    @Test
    fun `workspace always points at clarice`() {
        // Second Mind has no tasks, no day and no agenda. Whatever capture is
        // doing, these two have exactly one place to go.
        assertEquals(clarice, Backends(clarice, secondMind).workspace.baseUrl)
        assertEquals(clarice, Backends(clarice, "").workspace.baseUrl)
    }

    @Test
    fun `capture goes to second mind once one is configured`() {
        assertEquals(secondMind, Backends(clarice, secondMind).capture.baseUrl)
    }

    @Test
    fun `capture falls back to clarice when no second mind is configured`() {
        // The safe default, and the reason this is additive: a build with no
        // -PsecondMindBaseUrl behaves exactly as every build did before.
        assertEquals(clarice, Backends(clarice, "").capture.baseUrl)
    }

    @Test
    fun `a blank second mind url is treated as unconfigured, not as a host`() {
        // buildConfigField cannot express "absent", so an unset property
        // arrives as the empty string, and whitespace is what a typo in a
        // gradle.properties line leaves behind.
        assertFalse(Backends(clarice, "   ").isSplit)
        assertEquals(clarice, Backends(clarice, "   ").capture.baseUrl)
    }

    @Test
    fun `a split install never shares a token between the two servers`() {
        // The failure this exists to prevent: one token store for both
        // connections would send Clarice's bearer token to Second Mind on
        // every capture, and Second Mind's to Clarice. Two servers, two
        // credentials, two slots -- enforced here rather than trusted to
        // whoever wires up MainActivity next.
        val split = Backends(clarice, secondMind)

        assertTrue(split.isSplit)
        assertNotEquals(split.capture.tokenAlias, split.workspace.tokenAlias)
        assertNotEquals(split.capture.tokenPrefs, split.workspace.tokenPrefs)
    }

    @Test
    fun `an unsplit install shares one token, so it needs one login`() {
        // The mirror of the rule above, and it matters just as much: when
        // both concerns face the same server, giving them separate slots
        // would ask someone to log in to Clarice twice and leave the second
        // connection silently unauthenticated.
        val single = Backends(clarice, "")

        assertFalse(single.isSplit)
        assertEquals(single.capture.tokenAlias, single.workspace.tokenAlias)
        assertEquals(single.capture.tokenPrefs, single.workspace.tokenPrefs)
    }

    @Test
    fun `an ordinary build is not split`() {
        // The guard on the build property itself, not just the class. Giving
        // SECOND_MIND_BASE_URL a default host would silently redirect every
        // capture in every build that did not ask for it -- somebody's
        // thoughts posted to a server they never chose. Empty is the only
        // safe default and this is what keeps it that way.
        assertFalse(Backends(BuildConfig.CLARICE_BASE_URL, BuildConfig.SECOND_MIND_BASE_URL).isSplit)
    }

    @Test
    fun `the workspace keeps the token slot every existing install already uses`() {
        // Existing phones hold a token under this alias and this preference
        // file. Renaming either would silently log everybody out and send
        // them back to Connect with no explanation -- and the workspace half
        // is the one that has to keep working untouched.
        val workspace = Backends(clarice, secondMind).workspace

        assertEquals("clarice_capture_token", workspace.tokenAlias)
        assertEquals("clarice_capture_secret", workspace.tokenPrefs)
    }
}
