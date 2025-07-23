# Text-to-JSONL Pipeline

A Streamlit-based web application for scraping content from web pages and PDFs, converting it into structured JSONL format, and comparing scraped data with live website content to detect changes. The application supports semantic similarity analysis, database management, and detailed content comparison.

## Features

- **Text-to-JSONL Pipeline**: Scrape content from URLs (web pages or PDFs) and save it as structured `.jsonl` files with metadata (e.g., headings, external links, last updated date).
- **Batch Comparison**: Compare scraped content against live website content to detect drift or changes using semantic similarity scores.
- **Content Comparison**: View side-by-side differences between scraped and live content with a detailed diff visualization.
- **Database Management**: View, validate, repair, and delete `.jsonl` databases containing scraped data.
- **PDF Processing**: Convert PDFs to markdown and extract structured content with semantic similarity analysis.
- **Real-time Logging**: Display detailed logs during scraping and processing for transparency.

## Requirements

### System Requirements
- **Operating System**: Windows, macOS, or Linux
- **Python**: Version 3.8 or higher
- **Web Browser**: Chrome, Firefox, or Edge for the Streamlit interface
- **Google Chrome**: Required for Selenium-based web scraping
- **ChromeDriver**: Automatically managed by `webdriver-manager`

### Python Dependencies
Install the required Python packages using the provided `requirements.txt`:

```bash
pip install -r requirements.txt
```

**requirements.txt**:
```
streamlit>=1.47.0,<2.0.0
pandas>=2.2.3,<3.0.0
requests>=2.32.3,<3.0.0
validators>=0.35.0,<1.0.0
beautifulsoup4>=4.13.4,<5.0.0
selenium>=4.34.2,<5.0.0
webdriver-manager>=4.0.2,<5.0.0
sentence-transformers>=5.0.0,<6.0.0
docling>=2.41.0,<3.0.0
torch>=2.7.1,<3.0.0
lxml>=5.4.0,<6.0.0
```

**Optional**: For GPU acceleration with `sentence-transformers`, install a CUDA-compatible version of PyTorch from [pytorch.org](https://pytorch.org/get-started/locally/).

## Installation

1. **Clone the Repository** (if applicable):
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Set Up a Virtual Environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Directory Structure**:
   Ensure the following directories are writable:
   - `database/`: Stores `.jsonl` files with scraped data.
   - `cache/`: Stores cached comparison results.
   - `logs/`: Stores error logs from web scraping.

   The application creates these directories automatically if they don't exist.

## Usage

The application consists of four main Streamlit pages, each with specific functionality:

### 1. Text-to-JSONL Pipeline (`_Text_to_JSONL_Pipeline.py`)
- **Purpose**: Scrape content from web pages or PDFs and save it as `.jsonl` files.
- **How to Use**:
  1. Run: `streamlit run _Text_to_JSONL_Pipeline.py`
  2. Enter a database name (without `.jsonl` extension).
  3. Input URLs (one per line) for web pages or PDFs.
  4. Click "Run Pipeline" to scrape content and save it to the specified database.
  5. View real-time logs and semantic similarity scores comparing scraped content to live content.

### 2. Batch Compare Scraped Data (`3_📊_Batch_Compare_Scraped_Data.py`)
- **Purpose**: Compare all scraped content in a database against live website content to detect changes.
- **How to Use**:
  1. Run: `streamlit run 3_📊_Batch_Compare_Scraped_Data.py`
  2. Select a database or choose "All Databases."
  3. Click "Run" to start batch processing.
  4. View a table of similarity scores, content lengths, and status indicators.
  5. Use the "Stop" button to halt processing if needed.

### 3. Compare Scraped Data with Website (`2_🔍_Compare_Scraped_Data_with_Website.py`)
- **Purpose**: Perform a detailed comparison of scraped content for a specific URL against its live version.
- **How to Use**:
  1. Run: `streamlit run 2_🔍_Compare_Scraped_Data_with_Website.py`
  2. Enter a URL to compare.
  3. Select a database if multiple databases contain the URL.
  4. Click "Fetch and compare live page" to view:
     - Semantic similarity score
     - Side-by-side text preview
     - HTML diff visualization
     - Full-screen content details with metadata and external links

### 4. View and Manage Databases (`1_📚_View_and_Manage_Databases.py`)
- **Purpose**: View, validate, repair, and delete `.jsonl` databases.
- **How to Use**:
  1. Run: `streamlit run 1_📚_View_and_Manage_Databases.py`
  2. Select a `.jsonl` file to view its contents as a table.
  3. Enable debugging options to view raw content, validation details, or repair corrupted files.
  4. Use the delete section to remove unwanted databases.

## File Structure

- **Main Scripts**:
  - `_Text_to_JSONL_Pipeline.py`: Main scraping and JSONL creation pipeline.
  - `3_📊_Batch_Compare_Scraped_Data.py`: Batch comparison of scraped vs. live content.
  - `2_🔍_Compare_Scraped_Data_with_Website.py`: Detailed comparison for a single URL.
  - `1_📚_View_and_Manage_Databases.py`: Database management interface.
- **Utility Scripts**:
  - `parsepdf.py`: PDF processing and markdown parsing.
  - `utils.py`: Shared utilities for web scraping, semantic similarity, and data loading.
  - `meta_utils.py`: Enhanced web scraping for specific site structures.
  - `batch_processing.py`: Cache management for batch comparisons.
- **Configuration**:
  - `requirements.txt`: Python dependencies.
- **Directories**:
  - `database/`: Stores `.jsonl` files.
  - `cache/`: Stores cached comparison results.
  - `logs/`: Stores error logs.

## Notes

- **Performance**: Web scraping with Selenium and PDF processing with Docling can be resource-intensive. Ensure sufficient memory and CPU resources.
- **Error Handling**: The application logs errors to `logs/fetch_errors.log` and provides repair options for corrupted `.jsonl` files.
- **Semantic Similarity**: Uses the `all-MiniLM-L6-v2` model from `sentence-transformers` for comparing content. Scores range from 0 to 1, with thresholds:
  - >0.95: Excellent match
  - >0.85: Minor differences
  - >0.70: Partial match
  - ≤0.70: Poor match
- **PDF Processing**: Requires downloadable PDFs. Ensure URLs are accessible and not behind paywalls or authentication.
- **Web Scraping**: Designed for sites with accordion-style content (e.g., University of Gothenburg). Modify selectors in `meta_utils.py` or `utils.py` for other site structures.

## Troubleshooting

- **ChromeDriver Issues**: Ensure Google Chrome is installed and up-to-date. `webdriver-manager` handles ChromeDriver compatibility.
- **PDF Processing Errors**: Verify that PDFs are not corrupted or password-protected.
- **Memory Issues**: Reduce the number of URLs processed in a single run or increase system memory.
- **Database Errors**: Use the repair option in the "View and Manage Databases" page to fix corrupted `.jsonl` files.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details (if applicable).

## Contact

For questions or issues, please open an issue on the repository or contact the project maintainer.

## Acknowledgements

This project includes adapted components from the following open-source projects:

- 📄 **[Docling](https://github.com/docling-project/docling)** – Used for PDF scraping and conversion to structured content.
- 🌐 **[koop46's web scraping tools](https://github.com/koop46)** – Used as the base for website scraping functionality.

We thank the original authors for making their work publicly available under open-source licenses.
