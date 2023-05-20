function showError(message) {
    var errorMessage = document.getElementById("error-message");
    errorMessage.innerText = message;
    errorMessage.style.display = "block";
    alert(message);
    window.location.href = "/"
}  