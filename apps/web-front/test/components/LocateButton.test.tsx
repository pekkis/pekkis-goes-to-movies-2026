// @vitest-environment happy-dom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LOCATE_WATCHDOG_MS, LocateButton } from "../../src/components/LocateButton.tsx";

afterEach(cleanup);

const withGeolocation = (impl: Geolocation["getCurrentPosition"]) =>
  Object.defineProperty(navigator, "geolocation", {
    value: { getCurrentPosition: impl },
    configurable: true,
  });

const renderInForm = () => {
  const submit = vi.fn((e: Event) => e.preventDefault());
  const { container } = render(
    <form onSubmit={(e) => submit(e.nativeEvent)}>
      <select name="kaupunki" defaultValue="tampere">
        <option value="">Valitse kaupunki</option>
        <option value="tampere">Tampere</option>
      </select>
      <LocateButton />
    </form>,
  );
  return { form: container.querySelector("form")!, submit };
};

describe("LocateButton", () => {
  it("fills in the location and names it, but leaves submitting to Hae", () => {
    withGeolocation((ok) =>
      ok({ coords: { latitude: 61.49781, longitude: 23.76099 } } as GeolocationPosition),
    );
    const { form, submit } = renderInForm();
    fireEvent.click(screen.getByRole("button", { name: "Käytä sijaintiani" }));
    const field = (name: string) => form.elements.namedItem(name) as HTMLInputElement;
    expect(field("lat").value).toBe("61.4978");
    expect(field("lon").value).toBe("23.7610");
    const city = form.elements.namedItem("kaupunki") as HTMLSelectElement;
    expect(city.value).toBe("");
    expect(city.options[0]!.text).toBe("Oma sijainti");
    expect(screen.getByRole("status").textContent).toBe("Sijainti haettu. Paina Hae.");
    expect(submit).not.toHaveBeenCalled();
  });

  it.each([
    [1, "Selain ei antanut sijaintia."],
    [2, "Sijaintia ei saatu. Tarkista, että sijaintipalvelut ovat päällä"],
    [3, "Sijaintia ei saatu ajoissa."],
  ])("says why when the browser answers with error %s", (code, text) => {
    withGeolocation((_ok, fail) => fail?.({ code } as GeolocationPositionError));
    renderInForm();
    fireEvent.click(screen.getByRole("button", { name: "Käytä sijaintiani" }));
    expect(screen.getByRole("status").textContent).toContain(text);
  });

  it("gives up on a browser that never answers, and can be pressed again", () => {
    vi.useFakeTimers();
    try {
      // The first request hangs (a dismissed permission prompt); keep its callback.
      let late: PositionCallback | undefined;
      withGeolocation((ok) => {
        late = ok;
      });
      const { form } = renderInForm();
      const press = () => fireEvent.click(screen.getByRole("button", { name: /sijainti/i }));
      press();
      expect(screen.getByRole("button").textContent).toBe("Haetaan sijaintia…");
      act(() => {
        vi.advanceTimersByTime(LOCATE_WATCHDOG_MS);
      });
      expect(screen.getByRole("status").textContent).toContain("Sijaintia ei saatu ajoissa.");
      expect(screen.getByRole("button").textContent).toBe("Käytä sijaintiani");

      // An answer to the abandoned request changes nothing.
      act(() => late?.({ coords: { latitude: 60, longitude: 25 } } as GeolocationPosition));
      expect(form.elements.namedItem("lat")).toBeNull();

      // Pressed again, the browser answers this time.
      withGeolocation((ok) =>
        ok({ coords: { latitude: 61.5, longitude: 23.76 } } as GeolocationPosition),
      );
      press();
      expect((form.elements.namedItem("lat") as HTMLInputElement).value).toBe("61.5000");
      expect(screen.getByRole("status").textContent).toBe("Sijainti haettu. Paina Hae.");
    } finally {
      vi.useRealTimers();
    }
  });
});
