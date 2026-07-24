const initialize = (inputSelector) => {
  const textInput = document.querySelector(inputSelector);
  const clearError = () => {
    textInput.classList.remove("is-invalid");
  };
  textInput.oninput = clearError;
  textInput.onclick = clearError;
};
