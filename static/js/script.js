document.addEventListener("DOMContentLoaded", () => {
    const selected = [];
    const maxUnits = 10;

    const unitElements = document.querySelectorAll(".champion");
    const unitList = document.getElementById("unit-list");
    const teamCodeDiv = document.getElementById("team-code");
    const generateBtn = document.getElementById("generate-code");
    const braveryBtn = document.getElementById("bravery");
    const minInput = document.getElementById("min-units");
    const maxInput = document.getElementById("max-units");
    const weightedToggle = document.getElementById("weighted-random");

    // Helper: pick random element from array
    function randomChoice(arr) {
        return arr[Math.floor(Math.random() * arr.length)];
    }

    // Handle champion selection (manual clicks)
    if (unitElements.length && unitList) {
        unitElements.forEach(el => {
            el.addEventListener("click", () => {
                const name = el.dataset.name;
                const index = selected.indexOf(name);
                if (index >= 0) {
                    selected.splice(index, 1);
                    el.classList.remove("selected");
                } else {
                    if (selected.length < maxUnits) {
                        selected.push(name);
                        el.classList.add("selected");
                    } else {
                        alert("You can only select up to 10 units.");
                    }
                }
                unitList.textContent = selected.join(", ");
            });
        });
    }

    // Generate team code (manual)
    if (generateBtn && teamCodeDiv) {
        generateBtn.addEventListener("click", () => {
            fetch("/generate_code", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ units: selected })
            })
            .then(res => res.json())
            .then(data => {
                teamCodeDiv.textContent = data.team_code;
            });
        });
    }

    // Bravery button
    if (braveryBtn && unitElements.length) {
        braveryBtn.addEventListener("click", () => {
            const allChamps = Array.from(unitElements).map(el => el.dataset.name);

            // Read min/max and enforce rules
            let min = parseInt(minInput?.value) || 1;
            let max = parseInt(maxInput?.value) || 10;
            if (min < 1) min = 1;
            if (max > 10) max = 10;
            if (min > max) min = max;

            const count = Math.floor(Math.random() * (max - min + 1)) + min;
            selected.length = 0; // reset selection

            if (weightedToggle?.checked) {
                const distribution = {
                    6: {1:2, 2:2, 3:1, 4:1, 5:0},
                    7: {1:2, 2:2, 3:2, 4:1, 5:0},
                    8: {1:2, 2:2, 3:2, 4:1, 5:1},
                    9: {1:2, 2:2, 3:2, 4:2, 5:1},
                    10:{1:2, 2:2, 3:2, 4:2, 5:2}
                };

                const plan = distribution[count] || {};
                const costGroups = {};

                unitElements.forEach(el => {
                    const name = el.dataset.name;
                    const costGroupEl = el.closest(".cost-group")?.querySelector(".cost-title")?.textContent;
                    const cost = costGroupEl ? parseInt(costGroupEl[0]) : 1;
                    if (!costGroups[cost]) costGroups[cost] = [];
                    costGroups[cost].push(name);
                });

                for (let cost = 1; cost <= 5; cost++) {
                    const picks = plan[cost] || 0;
                    const pool = [...(costGroups[cost] || [])];

                    for (let i = 0; i < picks && pool.length > 0; i++) {
                        const choice = randomChoice(pool);
                        selected.push(choice);
                        pool.splice(pool.indexOf(choice), 1);
                    }
                }
            } else {
                const shuffled = allChamps.sort(() => 0.5 - Math.random());
                for (let i = 0; i < count; i++) {
                    selected.push(shuffled[i]);
                }
            }

            // Update UI
            unitElements.forEach(el => {
                el.classList.toggle("selected", selected.includes(el.dataset.name));
            });
            unitList.textContent = selected.join(", ");

            if (teamCodeDiv) {
                fetch("/generate_code", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ units: selected })
                })
                .then(res => res.json())
                .then(data => {
                    teamCodeDiv.textContent = data.team_code;
                });
            }
        });
    }

    // Toggle other participants in match summary cards
    document.querySelectorAll(".show-other-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const otherPlayers = btn.nextElementSibling;
            if (otherPlayers) {
                if (otherPlayers.style.display === "none") {
                    otherPlayers.style.display = "block";
                    btn.textContent = "Hide Other Participants";
                } else {
                    otherPlayers.style.display = "none";
                    btn.textContent = "Show Other Participants";
                }
            }
        });
    });
});
