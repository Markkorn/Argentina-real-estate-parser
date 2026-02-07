const fields = {
  listingType: "listingType",
  baseUrl: "baseUrl",
  pageParam: "pageParam",
  startPage: "startPage",
  endPage: "endPage",
  listingsSelector: "listingsSelector",
  titleSelector: "titleSelector",
  priceSelector: "priceSelector",
  locationSelector: "locationSelector",
  urlSelector: "urlSelector",
  urlAttribute: "urlAttribute",
  minPrice: "minPrice",
  maxPrice: "maxPrice",
  titleKeywords: "titleKeywords",
  locationKeywords: "locationKeywords",
  sleepSeconds: "sleepSeconds",
  outputPath: "outputPath",
  userAgent: "userAgent",
};

const getFieldValue = (id) => document.getElementById(id).value;

const parseKeywords = (value) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

const parseNumberOrNull = (value) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) && value !== "" ? numeric : null;
};

const buildConfig = () => ({
  base_url: getFieldValue(fields.baseUrl) || "https://example.com/rentals",
  page_param: getFieldValue(fields.pageParam) || "page",
  start_page: Number(getFieldValue(fields.startPage) || 1),
  end_page: Number(getFieldValue(fields.endPage) || 1),
  local_html_path: null,
  listing_type: getFieldValue(fields.listingType) || "rent",
  listings_selector: getFieldValue(fields.listingsSelector),
  title_selector: getFieldValue(fields.titleSelector),
  price_selector: getFieldValue(fields.priceSelector),
  location_selector: getFieldValue(fields.locationSelector),
  url_selector: getFieldValue(fields.urlSelector),
  url_attribute: getFieldValue(fields.urlAttribute) || "href",
  headers: {
    "User-Agent": getFieldValue(fields.userAgent),
  },
  sleep_seconds: Number(getFieldValue(fields.sleepSeconds) || 0),
  output_path: getFieldValue(fields.outputPath),
  min_price: parseNumberOrNull(getFieldValue(fields.minPrice)),
  max_price: parseNumberOrNull(getFieldValue(fields.maxPrice)),
  title_keywords_include: parseKeywords(getFieldValue(fields.titleKeywords)),
  location_keywords_include: parseKeywords(getFieldValue(fields.locationKeywords)),
});

const renderConfig = () => {
  const output = document.getElementById("configOutput");
  output.textContent = JSON.stringify(buildConfig(), null, 2);
};

const copyConfig = async () => {
  const text = document.getElementById("configOutput").textContent;
  await navigator.clipboard.writeText(text);
  const button = document.getElementById("copyButton");
  const original = button.textContent;
  button.textContent = "Скопировано";
  setTimeout(() => {
    button.textContent = original;
  }, 1500);
};

const downloadConfig = () => {
  const blob = new Blob([document.getElementById("configOutput").textContent], {
    type: "application/json",
  });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "parser_config.json";
  link.click();
  URL.revokeObjectURL(link.href);
};

Object.values(fields).forEach((id) => {
  document.getElementById(id).addEventListener("input", renderConfig);
});

document.getElementById("copyButton").addEventListener("click", copyConfig);

document
  .getElementById("downloadButton")
  .addEventListener("click", downloadConfig);

renderConfig();
