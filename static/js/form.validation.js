document.addEventListener('DOMContentLoaded', function() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const numberInputs = form.querySelectorAll('input[type="number"][min="0"]');
            let valid = true;
            
            numberInputs.forEach(input => {
                const value = parseFloat(input.value);
                if (value < 0) {
                    valid = false;
                    input.classList.add('error');
                    showError(input, '数值不能为负数');
                } else {
                    input.classList.remove('error');
                    clearError(input);
                }
            });
            
            if (!valid) {
                e.preventDefault();
            }
        });
    });
    
    const numberInputs = document.querySelectorAll('input[type="number"]');
    numberInputs.forEach(input => {
        input.addEventListener('input', function() {
            const min = parseFloat(this.getAttribute('min'));
            if (min !== null && !isNaN(min) && parseFloat(this.value) < min) {
                this.classList.add('error');
            } else {
                this.classList.remove('error');
            }
        });
    });
});

function showError(input, message) {
    clearError(input);
    const errorDiv = document.createElement('div');
    errorDiv.className = 'form-error';
    errorDiv.textContent = message;
    input.parentNode.appendChild(errorDiv);
}

function clearError(input) {
    const existingError = input.parentNode.querySelector('.form-error');
    if (existingError) {
        existingError.remove();
    }
}

document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        const messages = document.querySelectorAll('.message');
        messages.forEach(message => {
            message.style.opacity = '0';
            message.style.transition = 'opacity 0.5s ease';
            setTimeout(() => {
                message.style.display = 'none';
            }, 500);
        });
    }, 3000);
});
