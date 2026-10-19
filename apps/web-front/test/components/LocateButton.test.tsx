// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocateButton } from "../../src/components/LocateButton.tsx";

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

  it("says so when the location can't be had", () => {
    withGeolocation((_ok, fail) => fail?.({ code: 1 } as GeolocationPositionError));
    renderInForm();
    fireEvent.click(screen.getByRole("button", { name: "Käytä sijaintiani" }));
    expect(screen.getByRole("status").textContent).toBe("Sijaintia ei saatu. Valitse kaupunki.");
  });
});
