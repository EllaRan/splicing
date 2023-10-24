import pandas as pd
from tqdm import tqdm
import json
import sys
import random
import pickle
import argparse
import matplotlib.pyplot as plt
import seaborn as sns
import sys

DEF_DATA_PATH = "../data/united_species_dataset.pkl"

def load_metadata(chosen_species='human'):
    """ read metadata files from each species and concat them to one dataframe """
    if chosen_species == 'human':
        meta_data = pd.read_csv("../data/human_length.tsv", sep="\t",
                                names=['Gene stable ID', 'transcript_id', 'transcript_start', 'transcript_end',
                                       'Chromosome'], low_memory=False).set_index('transcript_id')
        meta_data['transcript_len'] = meta_data['transcript_end'] - meta_data['transcript_start'] + 1
        return meta_data
    elif chosen_species == 'mouse':
        meta_data = pd.read_csv("../data/mouse_length.tsv", sep="\t",
                                names=['Gene stable ID', 'transcript_id', 'transcript_start', 'transcript_end',
                                       'Chromosome']).set_index('transcript_id')
        meta_data['transcript_len'] = meta_data['transcript_end'] - meta_data['transcript_start'] + 1
        return meta_data


def load_exons(exons_path):
    exon_loaded = pd.read_pickle(exons_path)
    exon_loaded.set_index('exon_id', inplace=True)
    exon_loaded['exon_len'] = exon_loaded['exon_end'] - exon_loaded['exon_start'] + 1
    return exon_loaded
    
def load_data(path_to_data=DEF_DATA_PATH):
    loaded_data = pd.read_pickle(path_to_data)
    loaded_data['gene_id'] = loaded_data.index.map(lambda x: x.split('|')[0])
    loaded_data['transcript_id'] = loaded_data.index.map(lambda x: x.split('|')[2])
    loaded_data['unspliced_len'] = loaded_data['unspliced_transcript'].apply(lambda x: len(x))
    loaded_data['coding_seq_len'] = loaded_data['coding_seq'].apply(lambda x: len(x))
    loaded_data.reset_index(inplace=True)
    loaded_data.set_index('transcript_id', inplace=True)
    loaded_data = loaded_data[
        ['gene_id', 'unspliced_transcript', 'coding_seq', 'gene_id', 'unspliced_len', 'coding_seq_len', 'species']]
    return loaded_data

def find_transcripts_to_filter(dataset, metadata):
    all_transcripts = dataset.index
    common_transcripts = all_transcripts.intersection(metadata.index)

    different_len = [transcript for transcript in common_transcripts if
                     dataset.loc[transcript]['unspliced_len'] != metadata.loc[transcript]['transcript_len']]
    not_found = [transcript for transcript in all_transcripts if transcript not in common_transcripts]
    return different_len, not_found
    
def filter_by_chromosome(metadata, chromosome_arr, data):
    """ filter by chromosome and return only transcripts with unspliced_len == transcript_len"""
    merged_data = data.merge(metadata, left_index=True, right_index=True)
    merged_data = merged_data[merged_data['Chromosome'].isin(chromosome_arr)]
    return merged_data[merged_data['unspliced_len'] == merged_data['transcript_len']]

def get_exon_intron_lists(dataset, metadata, not_found):
    encoded_transcripts = {}
    not_same_spliced_length = []
    start_end_exons_all = {}
    start_end_introns_all = {}
    for transcript in tqdm(dataset.index):
        if transcript in different_len or transcript in not_found: continue
        exons = all_exons[all_exons['transcript_id'] == transcript].sort_values(by='exon_start', ascending=True)
        transcript_data = data.loc[transcript]
        encoded_seq = [0 for i in range(transcript_data['unspliced_len'])]
        transcript_start_genome = metadata.loc[transcript]['transcript_start']
        start_end_exons_all[transcript] = []
        start_end_introns_all[transcript] = []
        for exon, exon_data in exons.iterrows():
            start = exon_data['exon_start'] - transcript_start_genome
            end = exon_data['exon_end'] - transcript_start_genome
            # create start,end tuples for exons
            start_end_exons_all[transcript].append([start, end])
            # update encoded_seq
            for i in range(start, end + 1):
                encoded_seq[i] = 1

        # create start,end tuples for introns
        for i in range(len(start_end_exons_all[transcript]) - 1):
            start_intron = start_end_exons_all[transcript][i][1] + 1
            end_intron = start_end_exons_all[transcript][i + 1][0] - 1
            start_end_introns_all[transcript].append([start_intron, end_intron])
        ##

        # assert that sum of encoded seq == coding_seq_len
        if sum(encoded_seq) != transcript_data['coding_seq_len']: not_same_spliced_length.append(transcript)
        encoded_transcripts[transcript] = encoded_seq

    return encoded_transcripts, start_end_exons_all, start_end_introns_all


def encode_transcripts(data, metadata, all_exons):
    encoded_transcripts_dict = {}
    for transcript in tqdm(data.index):

        exons = all_exons[all_exons['transcript_id'] == transcript].sort_values(by='exon_start', ascending=True)
        transcript_data = data.loc[transcript]

        encoded_seq = [0 for i in range(transcript_data['unspliced_len'])]
        transcript_start_genome = metadata.loc[transcript]['transcript_start']

        for exon, exon_data in exons.iterrows():
            start = exon_data['exon_start'] - transcript_start_genome
            end = exon_data['exon_end'] - transcript_start_genome
            for i in range(start, end + 1):
                encoded_seq[i] = 1
        encoded_transcripts_dict[transcript] = encoded_seq

    return encoded_transcripts_dict
 
#analysis functions
def print_statistics(df):
    with open("statistics.txt", "w") as file:
        sys.stdout = file

        num_genes = df['Gene stable ID'].nunique()
        print(f'Number of genes in the data: {num_genes}')

        transcript_counts = df.groupby('Gene stable ID').size().reset_index(name='Count')
        transcript_counts.set_index('Gene stable ID', inplace=True)
        avg_transcript_num = transcript_counts['Count'].mean()
        print(f'Average number of transcripts per gene: {avg_transcript_num:.3f}')
        std_transcript_num = transcript_counts['Count'].std()
        print(f'Standard deviation of the number of transcripts per gene: {std_transcript_num:.3f}')


def load_obj(path):
    with open(path + '.pkl', 'rb') as f:
        return pickle.load(f)


def create_transcript_length_hist(df):
    fig, ax = plt.subplots(figsize=(8, 6))

    # Plot the histogram with custom styling
    ax.hist(df['transcript_len'], bins=20, edgecolor='k')
    ax.set_yscale('log')
    ax.set_xlabel('Length')
    ax.set_ylabel('Counts')
    ax.set_title('Transcripts Length Values', fontsize=16)
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    plt.savefig('transcript_length_hist.png')
    plt.close()


def get_percentage_spliced(labels_dict):
    percentage_dict = {}
    for transcript, labels in labels_dict.items():
        ones_count = labels.count(1)
        total_count = len(labels)
        percentage = ones_count / total_count
        percentage_dict[transcript] = percentage
    return percentage_dict


def create_exon_proportion_hist(exon_freq_dict):
    # Create a DataFrame from the dictionary
    df = pd.DataFrame(exon_freq_dict.items(), columns=['Key', 'Percentage'])

    # Create a density plot using Seaborn
    sns.set(style="whitegrid")  # Set the style
    plt.figure(figsize=(8, 4))  # Set the figure size
    sns.histplot(data=df['Percentage'], color='skyblue')

    # Customize the plot
    plt.ylabel('Counts')
    plt.xlabel('Proportion of Nucleotides in Exons Among Unspliced Transcripts')
    plt.title('Proportion of Nucleotides in Exons Among Unspliced Transcripts', fontsize=16)
    plt.savefig('exon_proportion_hist.png', bbox_inches='tight')
    plt.close()
    
if __name__ == '__main__':
    #load arguments
    parser = argparse.ArgumentParser()
    
    parser.add_argument('-d', '--data_path', type=str)
    parser.add_argument('-chrm', '--chosen_chromosomes', nargs='+', type=int)
    
    args = parser.parse_args()    
    
    data_path = args.data_path
    chosen_chromosomes = args.chosen_chromosomes
    chosen_chromosomes = list(map(str, chosen_chromosomes))
    
    #run pipeline
    metadata = load_metadata()
    metadata = metadata[~metadata.index.duplicated(keep='first')]
    all_exons = load_exons("../data/all_exons.pkl")
    data = load_data(data_path)
    print("all data loaded")
    
    ##calculate
    #different_len, not_found = find_transcripts_to_filter(data, metadata)
    #data_filtered_by_chromosome = filter_by_chromosome(metadata, chosen_chromosomes, data)
    
    #load
    not_found = load_obj(f"../load_for_data/not_found_train")
    not_found_test = load_obj(f"../load_for_data/not_found_test")
    not_found.extend(not_found_test)

    different_len = load_obj(f"../load_for_data/different_len_train")
    different_len_test = load_obj(f"../load_for_data/different_len_test")
    different_len.extend(different_len_test)
    
    data_filtered_by_chromosome_train = load_obj(f"../load_for_data/data_filtered_by_chromosome_train")
    data_filtered_by_chromosome_test = load_obj(f"../load_for_data/data_filtered_by_chromosome_test")
    data_filtered_by_chromosome = pd.concat([data_filtered_by_chromosome_train, data_filtered_by_chromosome_test])
    print("data filtered")
    
    # _, start_end_exons_all, start_end_introns_all = get_exon_intron_lists(data_filtered_by_chromosome, metadata,
                                                                          # not_found)
    # print(len(start_end_exons_all))
    
    ##calculate
    #encoded_transcripts = encode_transcripts(data_filtered_by_chromosome, metadata, all_exons)
    
    #load
    encoded_transcripts = load_obj(f"../load_for_data/encoded_transcripts_train")
    encoded_transcripts_test = load_obj(f"../load_for_data/encoded_transcripts_test")
    encoded_transcripts.update(encoded_transcripts_test)
    print("encoded transcripts")
    
    print_statistics(metadata)
    sys.stdout = sys.__stdout__
    create_transcript_length_hist(metadata)
    encoded_freq_transcripts_dict = get_percentage_spliced(encoded_transcripts)
    create_exon_proportion_hist(encoded_freq_transcripts_dict)
    