let people = 4;

function changePeople(n) {
    people += n;
    if (people < 1) people = 1;
    if (people > 12) people = 12;

    const input = document.getElementById("people");
    const summary = document.getElementById("summary");
    if (input) input.value = people;
    if (summary) summary.innerText = people;
}

function toggleChoice(button) {
    button.classList.toggle("selected");
    updateSelections();
}

function selectSingle(button) {
    const group = button.dataset.single;
    document.querySelectorAll(`[data-single="${group}"]`).forEach(item => item.classList.remove("selected"));
    button.classList.add("selected");

    const target = document.getElementById(group === "trip_type" ? "trip_type" : "accommodation_type");
    if (target) target.value = button.dataset.value;
}

function updateSelections() {
    const transport = [...document.querySelectorAll('[data-group="transport"].selected')]
        .map(button => button.dataset.value);
    const interests = [...document.querySelectorAll('[data-group="interest"].selected')]
        .map(button => button.dataset.value);

    const transportInput = document.getElementById("transport_preference");
    const interestsInput = document.getElementById("interests");
    if (transportInput) transportInput.value = transport.join(", ");
    if (interestsInput) interestsInput.value = interests.join(", ");
}

function planTrip() {
    const form = document.getElementById("tripForm");
    if (form) {
        updateSelections();
        form.requestSubmit();
    }
}

document.addEventListener("DOMContentLoaded", function () {
    updateSelections();

    const start = document.getElementById("start_date");
    const end = document.getElementById("end_date");
    if (start && end) {
        start.addEventListener("change", function () {
            end.min = start.value;
            if (end.value && end.value < start.value) end.value = start.value;
        });
    }
});
