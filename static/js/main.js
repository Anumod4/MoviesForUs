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

    // Video streaming and playback optimization
    const videoElements = document.querySelectorAll('video');
    
    videoElements.forEach(video => {
        // Preload video metadata
        video.preload = 'metadata';
        
        // Improve buffering and playback
        video.addEventListener('loadstart', function() {
            console.log('Video loading started');
        });
        
        video.addEventListener('canplay', function() {
            console.log('Video can start playing');
            // Optional: Attempt to preload more of the video
            video.play().catch(e => {
                console.warn('Autoplay prevented:', e);
            });
        });
        
        video.addEventListener('progress', function() {
            // Log buffering progress
            const buffered = video.buffered;
            if (buffered.length > 0) {
                const bufferedEnd = buffered.end(buffered.length - 1);
                const duration = video.duration;
                console.log(`Buffered: ${(bufferedEnd / duration * 100).toFixed(2)}%`);
            }
        });
        
        // Error handling
        video.addEventListener('error', function(e) {
            console.error('Video loading error:', e);
            alert('Error loading video. Please try again or check your connection.');
        });
    });

    // Video Performance Tracking
    const videoElementsPerformance = document.querySelectorAll('video');
    
    videoElementsPerformance.forEach(video => {
        // Performance tracking variables
        let startLoadTime = 0;
        let endLoadTime = 0;
        
        // Load start tracking
        video.addEventListener('loadstart', function() {
            startLoadTime = performance.now();
            console.log('Video loading started');
        });
        
        // Buffering tracking
        video.addEventListener('waiting', function() {
            console.log('Video buffering started');
        });
        
        // Playback ready tracking
        video.addEventListener('canplay', function() {
            endLoadTime = performance.now();
            const loadDuration = endLoadTime - startLoadTime;
            
            console.log(`Video load time: ${loadDuration.toFixed(2)}ms`);
            
            // Network information logging
            const connection = navigator.connection || 
                               navigator.mozConnection || 
                               navigator.webkitConnection;
            
            if (connection) {
                console.log('Network Type:', connection.effectiveType);
                console.log('Downlink Speed:', connection.downlink, 'Mbps');
            }
        });
        
        // Detailed buffering progress
        video.addEventListener('progress', function() {
            const buffered = video.buffered;
            if (buffered.length > 0) {
                const bufferedEnd = buffered.end(buffered.length - 1);
                const duration = video.duration;
                const bufferedPercentage = (bufferedEnd / duration * 100).toFixed(2);
                
                console.log(`Buffered: ${bufferedPercentage}%`);
            }
        });
        
        // Error tracking
        video.addEventListener('error', function(e) {
            console.error('Video Error:', e);
            console.error('Error Code:', video.error.code);
            console.error('Error Message:', video.error.message);
        });
    });

    // Optional: Bandwidth and performance tracking
    if ('performance' in window) {
        window.addEventListener('load', function() {
            const connection = navigator.connection || 
                               navigator.mozConnection || 
                               navigator.webkitConnection;
            
            if (connection) {
                console.log('Network Type:', connection.type);
                console.log('Effective Bandwidth:', connection.downlink, 'Mbps');
            }
        });
    }

    // Upload Progress Tracking
    const uploadForms = document.querySelectorAll('form[enctype="multipart/form-data"]');
    
    uploadForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const uploadButton = form.querySelector('button[type="submit"]');
            const progressContainer = form.querySelector('.upload-progress-container');
            const progressBar = form.querySelector('.upload-progress-bar');
            
            if (progressContainer && progressBar) {
                progressContainer.style.display = 'block';
                uploadButton.disabled = true;
                
                const xhr = new XMLHttpRequest();
                
                xhr.upload.onprogress = function(event) {
                    if (event.lengthComputable) {
                        const percentComplete = Math.round((event.loaded / event.total) * 100);
                        progressBar.style.width = `${percentComplete}%`;
                        progressBar.textContent = `${percentComplete}%`;
                    }
                };
                
                xhr.onload = function() {
                    uploadButton.disabled = false;
                    
                    if (xhr.status === 200) {
                        progressBar.classList.remove('bg-warning');
                        progressBar.classList.add('bg-success');
                        progressBar.style.width = '100%';
                        progressBar.textContent = 'Upload Complete';
                    } else {
                        progressBar.classList.remove('bg-warning');
                        progressBar.classList.add('bg-danger');
                        progressBar.textContent = 'Upload Failed';
                    }
                };
                
                xhr.onerror = function() {
                    uploadButton.disabled = false;
                    progressBar.classList.remove('bg-warning');
                    progressBar.classList.add('bg-danger');
                    progressBar.textContent = 'Network Error';
                };
            }
        });
    });
});
