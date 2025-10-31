document.addEventListener("DOMContentLoaded", () => {
  const availableCheckbox = document.getElementById("availableCheckbox");
  const priceRange = document.getElementById("priceRange");
  const priceValue = document.getElementById("priceValue");
  const togglePriceButton = document.getElementById("togglePrice");
  const restaurantSelect = document.getElementById("restaurantSelect");
  const searchForm = document.getElementById("searchForm");
  const titleInput = document.getElementById("titleInput");
  const descriptionInput = document.getElementById("descriptionInput");
  const searchModeRadios = document.querySelectorAll('input[name="searchMode"]');
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

  const renderResults = (items, mode, message) => {
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
      title.textContent = item.product?.name ?? item.title ?? "Producto sin nombre";
      li.appendChild(title);

      if (item.title) {
        const titleHighlight = document.createElement("p");
        titleHighlight.classList.add("result-title");
        titleHighlight.textContent = `Título: ${item.title}`;
        li.appendChild(titleHighlight);
      }

      if (item.product?.description) {
        const description = document.createElement("p");
        description.textContent = item.product.description;
        li.appendChild(description);
      }

      const meta = document.createElement("div");
      meta.classList.add("result-meta");
      const baseMeta = [
        `<span><strong>Restaurante:</strong> ${item.restaurantName ?? "N/D"}</span>`,
        `<span><strong>Disponible:</strong> ${item.product?.available ? "Sí" : "No"}</span>`,
        `<span><strong>Precio:</strong> S/${Number(item.product?.price?.amount ?? 0).toFixed(2)}</span>`,
      ];

      if (mode === "hybrid" && item.scoreDetails) {
        const fusionScore =
          (item.scoreDetails?.fusion && item.scoreDetails.fusion.score) ?? null;
        const vectorScore =
          (item.scoreDetails?.vectorPipeline && item.scoreDetails.vectorPipeline.score) ?? null;
        const textScore =
          (item.scoreDetails?.fullTextPipeline && item.scoreDetails.fullTextPipeline.score) ?? null;

        baseMeta.push(
          `<span><strong>Score combinado:</strong> ${
            fusionScore !== null ? Number(fusionScore).toFixed(4) : "N/D"
          }</span>`
        );
        baseMeta.push(
          `<span><strong>Score vector:</strong> ${
            vectorScore !== null ? Number(vectorScore).toFixed(4) : "N/D"
          }</span>`
        );
        baseMeta.push(
          `<span><strong>Score texto:</strong> ${
            textScore !== null ? Number(textScore).toFixed(4) : "N/D"
          }</span>`
        );
      } else if (mode === "fulltext" && typeof item.score === "number") {
        baseMeta.push(
          `<span><strong>Score texto:</strong> ${Number(item.score).toFixed(4)}</span>`
        );
      } else if (typeof item.score === "number") {
        baseMeta.push(
          `<span><strong>Score vector:</strong> ${Number(item.score).toFixed(4)}</span>`
        );
      }

      meta.innerHTML = baseMeta.join("");
      li.appendChild(meta);

      resultsList.appendChild(li);
    });

    resultsSection.classList.remove("hidden");
  };

  if (searchForm) {
    searchForm.addEventListener("submit", (event) => {
      event.preventDefault();

      const selectedMode =
        Array.from(searchModeRadios).find((radio) => radio.checked)?.value ?? "vector";
      const descriptionValue = (descriptionInput?.value ?? "").trim();
      const titleValue = (titleInput?.value ?? "").trim();

      if (selectedMode !== "fulltext" && !descriptionValue) {
        alert("La descripción es obligatoria para la búsqueda vectorial o híbrida.");
        return;
      }

      if (selectedMode === "fulltext" && !titleValue) {
        alert("El título es obligatorio para la búsqueda full text.");
        return;
      }

      const payload = {
        mode: selectedMode,
        limit: 5,
      };

      if (selectedMode === "vector" || selectedMode === "hybrid") {
        payload.description = descriptionValue;
      }
      if (selectedMode !== "vector") {
        payload.title = titleValue;
      }

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
          renderResults(data.results ?? [], data.mode ?? selectedMode);
        })
        .catch((error) => {
          console.error(error);
          renderResults([], selectedMode, error.message);
        });
    });
  }
});
