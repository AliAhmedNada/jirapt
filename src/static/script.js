document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('jira-form');
    const resultOutput = document.getElementById('result-output');
    const submitButton = document.getElementById('submit-btn');

    form.addEventListener('submit', async (event) => {
        event.preventDefault(); // Prevent default form submission

        resultOutput.textContent = 'Processing... Please wait.';
        submitButton.disabled = true;
        submitButton.textContent = 'Creating...';

        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        try {
            // We will create this backend endpoint later
            const response = await fetch('/api/create_jira', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
            });

            const result = await response.json();

            if (response.ok) {
                resultOutput.textContent = `Success!\nStatus Code: ${result.status_code}\nResponse:\n${JSON.stringify(result.response, null, 2)}`;
                if (result.response && result.response.key) {
                    const issueUrl = `${data.jira_url.replace(/\/$/, '')}/browse/${result.response.key}`;
                    resultOutput.textContent += `\n\nIssue Link: ${issueUrl}`;
                }
            } else {
                resultOutput.textContent = `Error: ${response.status} ${response.statusText}\n${JSON.stringify(result, null, 2)}`;
            }
        } catch (error) {
            console.error('Error submitting form:', error);
            resultOutput.textContent = `An error occurred while contacting the backend: ${error.message}`;
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = 'Generate & Create Issue';
        }
    });
});
