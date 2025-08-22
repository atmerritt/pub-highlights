import logging
import textwrap
from pathlib import Path
from typing import cast

import click
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from pylatexenc.latex2text import LatexNodes2Text

from ph import retrieval

logger = logging.getLogger(__name__)
logging.basicConfig(format="%(asctime)s %(levelname)s:%(message)s", level=logging.INFO)


def collect_publications(
    search_string: str, window_days: int = 3, max_results: int = 100
) -> list[dict[str, str]]:
    """Collect abstracts."""
    pub_list = retrieval.call_arxiv_api(
        search_string, window_days=window_days, max_results=max_results
    )
    pub_list = retrieval.clean_results(pub_list)
    return pub_list


def generate_table(pub_list: list[dict[str, str]], max_width: int = 40) -> str:
    """Create a Markdown table to show all queried papers."""
    table = textwrap.dedent(
        """\
    # Complete publication list

    |     | Title | Author | Published | Updated | Category |
    | --- | ----- | ------ | --------- | ------- | -------- |
    """
    )

    for i, pub in enumerate(pub_list):
        table += (
            f"| {i + 1}"
            f"| {pub['title']} "
            f"| [{pub['author']} et al.]({pub['link']})"
            f"| {pub['published']} "
            f"| {pub['updated']} "
            f"| {pub['category']} |\n"
        )
    return table


def preprocess(paper: dict[str, str]) -> dict[str, str]:
    """Preprocessing."""
    # Create a classic citation-style reference for the paper
    paper["author"] = f"{paper['author'].split()[-1]} et al."

    # Convert latex to standard text
    paper["text"] = LatexNodes2Text().latex_to_text(paper["text"])

    # Remove keys we don't need
    paper.pop("updated")
    paper.pop("published")
    paper.pop("category")
    return paper


def generate_N_summaries(
    search_term: str,
    pub_list: list[dict[str, str]],
    model_name: str = "llama3.2:3b",
    n_summaries: int | None = 3,
) -> str:
    """Generate individual and high-level summaries for a set of abstracts.

    If N_summaries is None, then all abstracts will be summarized. Otherwise,
    the first 3 in the list (aka the 3 most recent) articles will be summarized.
    This is due to an apparent limitation of llama3.2:3b.
    """
    # Define prompt
    summary_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are an expert astronomer and researcher.

                Your task is to help your fellow researchers keep up with literature, by
                summarising papers or abstracts in their field, {field}, in two parts.

                ---

                Part 1: Paper descriptions
                For each of the following papers, you are given the paper title, paper
                author, paper link, and paper abstract text.
                Based on the paper abstract, please write a description of each paper,
                approximately a paragraph long.

                At minimum, the descriptions should include the following information
                about the paper:
                - the goal of the research
                - the data and methods used
                - any key findings
                - remaining open questions or caveats

                Please write in the third person, for example "The authors show that.."
                rather than "We show that.. "

                ---

                Part 2: High-level summary
                Please create a high-level summary, a couple paragraphs long, of
                everything that happened in the field of {field}, based on these papers.
                First, identify the key common themes, trends, or contradictions across
                the papers. For each key point, write a sentence or two and then
                directly follow it with a markdown-formatted citation to the paper(s)
                that support it using the paper author and link. For example, you
                might write: "One study shows that ... ([paper author](paper link))."

                ---

                This is scientific research, so if you do not know the answer to any of
                the above, DO NOT make up information.
                Stick to what you can learn from the text.

                Please format all output in Markdown.

                ---

                Here is an example of what the overall output should look like in
                Markdown if we had 2 papers:

                # Pub highlights
                ### paper 1 title ([paper 1 author](paper 1 link))
                description of paper 1

                ### paper 2 title ([paper 2 author](paper 2 link))
                description of paper 2


                # Summary
                [high-level summary of all papers]


                ---

                Here are the papers to work with:
                {input}


                """,
            ),
            ("human", "{input}"),
        ]
    )

    # Define model
    logger.info(f"Loading model: {model_name} ...")
    llm = ChatOllama(
        model=model_name,
        temperature=0,
        # other params...
    )

    # Pipe operator chains things together
    chain = summary_prompt | llm

    # Limit the set of abstracts to summarize if necessary
    if n_summaries is None:
        n_summaries = len(pub_list)
    else:
        pub_list = pub_list[:n_summaries]

    # Preprocess publication list for model inputs
    pub_list = [preprocess(pub) for pub in pub_list]

    logger.info(f"Summarizing {n_summaries} abstracts ...")
    summary_output = chain.invoke(
        {
            "field": search_term,
            "input": pub_list,
        }
    )
    return cast(str, summary_output.content)


@click.command()
@click.argument("search_term", type=str)
@click.option(
    "--window-days", type=int, default=7, help="Size of search window in days"
)
@click.option(
    "--max-results",
    type=int,
    default=200,
    help="Maximum number of publications to return. NOT recommended to change.",
)
@click.option(
    "--model-name",
    type=str,
    default="llama3.2:3b",
    help="Name of the model to use for this task",
)
@click.option(
    "--n-summaries",
    type=int,
    default=None,
    help="Number of abstracts to summarize (None = all)",
)
@click.option(
    "--out-dir",
    type=Path,
    default="latest",
    help="Output directory to store the summary Markdown pages",
)
def get_pub_highlights(
    search_term: str,
    window_days: int = 7,
    max_results: int = 100,
    model_name: str = "llama3.2:3b",
    n_summaries: int = 3,
    out_dir: Path = Path("latest"),
) -> None:
    # Read in and preprocess abstracts
    logger.info("Querying the arXiv API for publications...")
    logger.info(f"Field: {search_term}")
    logger.info(f"Window (days): {window_days}")
    logger.info(f"Max results: {max_results}")
    pub_list = collect_publications(
        search_term, window_days=window_days, max_results=max_results
    )

    # Create Markdown table
    logger.info(f"Generating a summary table for all {len(pub_list)} publications...")
    summary_table = generate_table(pub_list)

    # Summarize the top N abstracts
    summary_text = generate_N_summaries(
        search_term, pub_list, model_name=model_name, n_summaries=n_summaries
    )

    # Combine text and table
    md_text = summary_text + "\n" + summary_table

    # Write Markdown file
    output_filename = f"{out_dir}/{search_term.replace(' ', '_')}.md"
    logger.info(f"Writing results to file: {output_filename}")
    with open(output_filename, "w") as f:
        f.write(md_text)


if __name__ == "__main__":
    get_pub_highlights()
