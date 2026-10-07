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



// ==========================================
// DYNAMIC LOCATION SEARCH
// ==========================================

function setupLocationSearch(searchId, hiddenId, resultsId) {

    const searchInput = document.getElementById(searchId);
    const hiddenInput = document.getElementById(hiddenId);
    const resultsBox = document.getElementById(resultsId);

    if (!searchInput || !hiddenInput || !resultsBox) {
        return;
    }

    let searchTimer = null;


    searchInput.addEventListener("input", function () {

        const query = searchInput.value.trim();

        // Clear selected value when user changes text
        hiddenInput.value = "";

        clearTimeout(searchTimer);

        if (query.length < 2) {
            resultsBox.innerHTML = "";
            return;
        }

        resultsBox.innerHTML =
            '<div class="location-loading">Searching locations...</div>';


        searchTimer = setTimeout(async function () {

            try {

                const url =
                    "https://nominatim.openstreetmap.org/search" +
                    "?format=json" +
                    "&addressdetails=1" +
                    "&limit=5" +
                    "&q=" +
                    encodeURIComponent(query);


                const response = await fetch(url, {
                    headers: {
                        "Accept": "application/json"
                    }
                });


                if (!response.ok) {
                    throw new Error("Location search failed");
                }


                const locations = await response.json();


                resultsBox.innerHTML = "";


                if (locations.length === 0) {

                    resultsBox.innerHTML =
                        '<div class="location-empty">' +
                        'No location found.' +
                        '</div>';

                    return;
                }


                locations.forEach(function (location) {

                    const item = document.createElement("div");

                    item.className = "location-result";

                    item.textContent = location.display_name;


                    item.addEventListener("click", function () {

                        // Show selected location
                        searchInput.value = location.display_name;

                        // Store location for Flask
                        hiddenInput.value = location.display_name;

                        // Store coordinates for future map
                        searchInput.dataset.lat = location.lat;
                        searchInput.dataset.lon = location.lon;

                        // Hide suggestions
                        resultsBox.innerHTML = "";

                    });


                    resultsBox.appendChild(item);

                });


            } catch (error) {

                console.error("Location search error:", error);

                resultsBox.innerHTML =
                    '<div class="location-empty">' +
                    'Unable to search locations. Try again.' +
                    '</div>';
            }

        }, 500);

    });


    // Hide suggestions when clicking outside
    document.addEventListener("click", function (event) {

        if (!searchInput.contains(event.target) &&
            !resultsBox.contains(event.target)) {

            resultsBox.innerHTML = "";
        }

    });

}


// Initialize Source Search
setupLocationSearch(
    "source_search",
    "source",
    "source_results"
);


// Initialize Destination Search
setupLocationSearch(
    "destination_search",
    "destination",
    "destination_results"
);