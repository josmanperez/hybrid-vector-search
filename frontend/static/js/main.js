document.addEventListener("DOMContentLoaded", () => {
  const availableCheckbox = document.getElementById("availableCheckbox");
  const priceRange = document.getElementById("priceRange");
  const priceValue = document.getElementById("priceValue");
  const togglePriceButton = document.getElementById("togglePrice");
  const restaurantSelect = document.getElementById("restaurantSelect");
  const searchForm = document.getElementById("searchForm");
  const descriptionInput = document.getElementById("descriptionInput");
  const resultsSection = document.getElementById("results");
  const resultsList = document.getElementById("resultsList");

  let priceEnabled = false;

  const updatePriceDisplay = () => {
    if (!priceValue) return;
    priceValue.textContent = priceEnabled ? priceRange.value : "--";
  };

  if (priceRange) {
    priceRange.addEventListener("input", updatePriceDisplay);
  }

  if (togglePriceButton) {
    togglePriceButton.addEventListener("click", () => {
      priceEnabled = !priceEnabled;
      togglePriceButton.classList.toggle("active", priceEnabled);
      togglePriceButton.textContent = priceEnabled ? "Deshabilitar" : "Habilitar";
      if (priceRange) {
        priceRange.disabled = !priceEnabled;
      }
      updatePriceDisplay();
    });
  }

  updatePriceDisplay();

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

  const renderResults = (items, message) => {
    if (!resultsSection || !resultsList) {
      return;
    }

    resultsList.innerHTML = "";

    if (!items.length) {
      const li = document.createElement("li");
      li.textContent = message || "No se encontraron resultados.";
      resultsList.appendChild(li);
      resultsSection.classList.remove("hidden");
      return;
    }

    items.forEach((item) => {
      const li = document.createElement("li");
      li.classList.add("result-item");

      const title = document.createElement("h3");
      title.textContent = item.product?.name ?? "Producto sin nombre";
      li.appendChild(title);

      if (item.product?.description) {
        const description = document.createElement("p");
        description.textContent = item.product.description;
        li.appendChild(description);
      }

      const meta = document.createElement("div");
      meta.classList.add("result-meta");
      meta.innerHTML = `
        <span><strong>Restaurante:</strong> ${item.restaurantName ?? "N/D"}</span>
        <span><strong>Disponible:</strong> ${item.product?.available ? "Sí" : "No"}</span>
        <span><strong>Precio:</strong> S/${Number(item.product?.price?.amount ?? 0).toFixed(2)}</span>
      `;
      li.appendChild(meta);

      resultsList.appendChild(li);
    });

    resultsSection.classList.remove("hidden");
  };

  if (searchForm) {
    searchForm.addEventListener("submit", (event) => {
      event.preventDefault();

      const payload = {
        query: descriptionInput?.value ?? "",
        limit: 5,
      };

      if (availableCheckbox?.checked) {
        payload.available = true;
      }

      if (priceEnabled && priceRange) {
        payload.maxPrice = Number(priceRange.value);
      }

      if (restaurantSelect && restaurantSelect.value) {
        payload.restaurant = restaurantSelect.value;
      }

      fetch("/api/search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      })
        .then((response) => {
          if (!response.ok) {
            return response.json().then((error) => {
              throw new Error(error.message || "Error al buscar resultados.");
            });
          }
          return response.json();
        })
        .then((data) => {
          renderResults(data.results ?? []);
        })
        .catch((error) => {
          console.error(error);
          renderResults([], error.message);
        });
    });
  }
});
