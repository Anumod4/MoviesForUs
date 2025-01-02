// Show file name when a file is selected
document.addEventListener('DOMContentLoaded', function() {
    // File input handling
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(input => {
        input.addEventListener('change', function() {
            const fileLabel = this.closest('.custom-file-input').querySelector('.custom-file-label');
            const fileName = this.files[0]?.name;
            
            if (fileName) {
                fileLabel.innerHTML = `
                    <i class="fas fa-file-video me-2"></i>${fileName}
                `;
            }

            // Thumbnail preview
            if (this.id === 'thumbnail') {
                const previewContainer = document.getElementById('thumbnail-preview');
                previewContainer.innerHTML = ''; // Clear previous preview

                if (this.files && this.files[0]) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        const img = document.createElement('img');
                        img.src = e.target.result;
                        img.classList.add('img-fluid', 'rounded', 'max-height-200');
                        img.style.maxHeight = '200px';
                        img.style.objectFit = 'cover';
                        
                        const label = document.createElement('small');
                        label.classList.add('d-block', 'text-muted', 'mt-2');
                        label.textContent = 'Thumbnail Preview';
                        
                        previewContainer.appendChild(img);
                        previewContainer.appendChild(label);
                    }
                    reader.readAsDataURL(this.files[0]);
                }
            }
        });
    });

    // Form submission handling
    const uploadForm = document.getElementById('upload-form');
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            const spinner = document.querySelector('.spinner');
            const submitBtn = document.getElementById('submit-btn');
            
            spinner.style.display = 'inline-block';
            submitBtn.disabled = true;
            submitBtn.innerHTML = `
                <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                Uploading...
            `;
        });
    }

    // Drag and drop file upload
    const dropZones = document.querySelectorAll('.custom-file-input');
    dropZones.forEach(dropZone => {
        const input = dropZone.querySelector('input[type="file"]');
        const label = dropZone.querySelector('.custom-file-label');

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, highlight, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, unhighlight, false);
        });

        function highlight() {
            label.classList.add('bg-light');
        }

        function unhighlight() {
            label.classList.remove('bg-light');
        }

        dropZone.addEventListener('drop', handleDrop, false);

        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            input.files = files;
            
            const event = new Event('change');
            input.dispatchEvent(event);
        }
    });
});
