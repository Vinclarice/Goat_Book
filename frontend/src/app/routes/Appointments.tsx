import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { apiV1 } from "../../api/client";

/**
 * One thing that happens at a time whether or not you act.
 *
 * `design/superlists-2.0-plan.md` increment 7. Its own record because its life
 * cycle is different, and the whole of that difference shows here: **there is
 * no tick.** A task you did not do is unfinished; a dentist appointment you did
 * not attend still happened to the afternoon. Whether you went is a line you
 * write in the composer, never something this infers from a date having passed.
 */
export type Appointment = {
  public_id: string;
  text: string;
  starts_on: string;
  ends_on: string | null;
  starts_at: string | null;
  ends_at: string | null;
  location: string;
  notes: string;
  cancelled: boolean;
};

/**
 * When it is, said the way the record holds it.
 *
 * **Dates and a time apart, never assembled into an instant.** An all-day thing
 * has no time of day at all, and inventing midnight for it would put a weekend
 * away at 12am — which is the mistake the model was shaped to prevent.
 *
 * Formatted here rather than on the server because it is a rendering of two
 * fields the server sent as they are stored, the same split `ageLabel` keeps.
 */
export function whenItIs(appointment: Appointment) {
  const span = appointment.ends_on
    ? `${dayLabel(appointment.starts_on)} – ${dayLabel(appointment.ends_on)}`
    : dayLabel(appointment.starts_on);
  if (appointment.starts_at === null) return `${span} · all day`;
  const times = appointment.ends_at
    ? `${clock(appointment.starts_at)}–${clock(appointment.ends_at)}`
    : clock(appointment.starts_at);
  return `${span} · ${times}`;
}

function dayLabel(iso: string) {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
}

/** A stored time of day, in the reader's own convention.
 *
 * Parsed as a wall clock rather than an instant: "14:00:00" is two in the
 * afternoon wherever it is read, because the record carries no zone and is not
 * pretending to.
 */
function clock(value: string) {
  const [hours, minutes] = value.split(":");
  return new Date(1970, 0, 1, Number(hours), Number(minutes)).toLocaleTimeString(
    undefined,
    { hour: "numeric", minute: "2-digit" },
  );
}

/**
 * The day's appointment strip — what is on today, then what is coming up.
 *
 * **Above the list**, which is rule 9's shape: a fixed commitment is never
 * invisible for not having been chosen, and what the afternoon has to bend
 * around belongs where it is read first.
 *
 * Cancelled ones stay, struck — rule 6. They are a fact about the day, and a
 * row that vanished would make *"the parents' evening was cancelled"*
 * unanswerable a month later.
 */
export function Appointments({
  today,
  coming,
  day,
  editable,
}: {
  today: Appointment[];
  coming: Appointment[];
  day: string;
  editable: boolean;
}) {
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["day"] });
    queryClient.invalidateQueries({ queryKey: ["pool"] });
    queryClient.invalidateQueries({ queryKey: ["calendar"] });
  };

  const cancel = useMutation({
    mutationFn: async (publicId: string) => {
      const { error } = await apiV1.POST(
        "/api/v1/appointments/{public_id}/cancel",
        { params: { path: { public_id: publicId } } },
      );
      if (error) throw new Error("Couldn't cancel that.");
    },
    onSuccess: invalidate,
  });

  const remove = useMutation({
    mutationFn: async (publicId: string) => {
      const { error } = await apiV1.DELETE("/api/v1/appointments/{public_id}", {
        params: { path: { public_id: publicId } },
      });
      if (error) throw new Error("Couldn't remove that.");
    },
    onSuccess: invalidate,
  });

  if (today.length === 0 && coming.length === 0 && !editable) return null;

  return (
    <section className="space-y-2">
      <h2 className="text-sm font-bold">Appointments</h2>
      {today.length === 0 && coming.length === 0 && (
        <p className="text-sm text-muted-foreground">Nothing in the diary.</p>
      )}
      {today.length > 0 && (
        <ul className="space-y-1">
          {today.map((each) => (
            <Row
              key={each.public_id}
              appointment={each}
              editable={editable}
              onCancel={() => cancel.mutate(each.public_id)}
              onRemove={() => remove.mutate(each.public_id)}
              busy={cancel.isPending || remove.isPending}
            />
          ))}
        </ul>
      )}
      {coming.length > 0 && (
        <>
          {/* Apart from today's, because they answer different questions:
              what the afternoon bends around, and what to keep in mind. */}
          <h3 className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
            Coming up
          </h3>
          <ul className="space-y-1">
            {coming.map((each) => (
              <Row
                key={each.public_id}
                appointment={each}
                editable={editable}
                onCancel={() => cancel.mutate(each.public_id)}
                onRemove={() => remove.mutate(each.public_id)}
                busy={cancel.isPending || remove.isPending}
              />
            ))}
          </ul>
        </>
      )}
      {editable &&
        (adding ? (
          <AppointmentForm
            day={day}
            onDone={() => {
              setAdding(false);
              invalidate();
            }}
            onCancel={() => setAdding(false)}
          />
        ) : (
          <Button type="button" variant="ghost" onClick={() => setAdding(true)}>
            Add an appointment
          </Button>
        ))}
    </section>
  );
}

function Row({
  appointment,
  editable,
  onCancel,
  onRemove,
  busy,
}: {
  appointment: Appointment;
  editable: boolean;
  onCancel: () => void;
  onRemove: () => void;
  busy: boolean;
}) {
  return (
    <li className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
      <span className="min-w-0">
        <span className={appointment.cancelled ? "line-through" : ""}>
          {appointment.text}
        </span>
        <span className="text-muted-foreground"> · {whenItIs(appointment)}</span>
        {appointment.location && (
          <span className="text-muted-foreground"> · {appointment.location}</span>
        )}
        {appointment.cancelled && (
          <span className="text-muted-foreground"> · cancelled</span>
        )}
      </span>
      {editable && (
        <span className="flex shrink-0 gap-2">
          {/* Two verbs, because they are two facts -- rule 6. Cancelling keeps
              the row on its day; removing is for something written down by
              mistake. */}
          {!appointment.cancelled && (
            <Button
              type="button"
              variant="ghost"
              disabled={busy}
              aria-label={`Cancel ${appointment.text}`}
              onClick={onCancel}
            >
              Cancel
            </Button>
          )}
          <Button
            type="button"
            variant="ghost"
            disabled={busy}
            aria-label={`Remove ${appointment.text}`}
            onClick={onRemove}
          >
            Remove
          </Button>
        </span>
      )}
    </li>
  );
}

/**
 * Writing one down.
 *
 * The date defaults to the day being looked at, and everything else is
 * optional — a diary entry somebody types in five seconds is words and a date,
 * which is exactly what the service requires and no more.
 */
function AppointmentForm({
  day,
  onDone,
  onCancel,
}: {
  day: string;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [text, setText] = useState("");
  const [startsOn, setStartsOn] = useState(day);
  const [endsOn, setEndsOn] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [location, setLocation] = useState("");
  const [notes, setNotes] = useState("");

  const make = useMutation({
    mutationFn: async () => {
      const { error } = await apiV1.POST("/api/v1/appointments", {
        body: {
          text,
          starts_on: startsOn,
          // Empty is not a value. An unset end date means *one day* and an
          // unset time means *all day*, and sending "" would be the client
          // asserting a third thing the record cannot hold.
          ends_on: endsOn || null,
          starts_at: startsAt || null,
          ends_at: endsAt || null,
          location,
          notes,
        },
      });
      if (error) throw new Error("Couldn't write that down. It's still here.");
    },
    onSuccess: onDone,
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!text.trim()) return;
    make.mutate();
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-2 rounded-lg border border-border px-3 py-2">
      <label htmlFor="appointment-text" className="text-sm font-bold">
        What is happening
      </label>
      <input
        id="appointment-text"
        value={text}
        onChange={(event) => setText(event.target.value)}
        className="w-full rounded-lg border border-border bg-input px-3 py-2 text-sm"
      />
      <div className="flex flex-wrap gap-3">
        <Field label="From" id="appointment-starts-on" type="date" value={startsOn} onChange={setStartsOn} />
        <Field label="To" id="appointment-ends-on" type="date" value={endsOn} onChange={setEndsOn} />
        <Field label="At" id="appointment-starts-at" type="time" value={startsAt} onChange={setStartsAt} />
        <Field label="Until" id="appointment-ends-at" type="time" value={endsAt} onChange={setEndsAt} />
      </div>
      <Field label="Where" id="appointment-location" type="text" value={location} onChange={setLocation} />
      <Field label="Notes" id="appointment-notes" type="text" value={notes} onChange={setNotes} />
      <div className="flex items-center gap-3">
        <Button type="submit" variant="secondary" disabled={make.isPending}>
          Add to the day
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Never mind
        </Button>
        {make.isError && (
          <span className="text-sm text-destructive">{make.error.message}</span>
        )}
      </div>
      <p className="text-sm text-muted-foreground">
        Leave the time blank for something that takes the whole day.
      </p>
    </form>
  );
}

function Field({
  label,
  id,
  type,
  value,
  onChange,
}: {
  label: string;
  id: string;
  type: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <span className="flex items-baseline gap-2">
      <label htmlFor={id} className="text-sm text-muted-foreground">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-lg border border-border bg-input px-2 py-1 text-sm"
      />
    </span>
  );
}
