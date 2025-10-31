document.addEventListener("DOMContentLoaded", () => {
  const priceRange = document.getElementById("priceRange");
  const priceValue = document.getElementById("priceValue");
  const restaurantSelect = document.getElementById("restaurantSelect");

  if (priceRange && priceValue) {
    priceValue.textContent = priceRange.value;
    priceRange.addEventListener("input", (event) => {
      priceValue.textContent = event.target.value;
    });
  }

  if (restaurantSelect) {
    fetch("/api/restaurants")
      .then((response) => {
        if (!response.ok) {
          throw new Error("No se pudo obtener el listado de restaurantes.");
        }
        return response.json();
      })
      .then((restaurants) => {
        restaurants.forEach((name) => {
          const option = document.createElement("option");
          option.value = name;
          option.textContent = name;
          restaurantSelect.appendChild(option);
        });
      })
      .catch((error) => {
        console.error(error);
      });
  }

  const form = document.getElementById("searchForm");
  if (form) {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      // Placeholder for search submission logic.
      console.log("Buscar:", {
        descripcion: document.getElementById("descriptionInput")?.value ?? "",
        disponible: document.getElementById("availableCheckbox")?.checked ?? false,
        precio: document.getElementById("priceRange")?.value ?? "",
        restaurante: restaurantSelect?.value ?? "",
      });
    });
  }
});
