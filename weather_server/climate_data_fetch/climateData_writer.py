def data_writer(filename, dates, data):
    with open(f"climate_data\{filename}", 'w') as f:
        # Specify data collection period
        f.write(f"start: {dates[0]}\n")
        f.write(f"end: {dates[-1]}\n")
        
        # Metadata separator
        f.write("=======================\n")

        # Each line is an array:
        for line in data:
            for i in range(len(line)):
                f.write(f"{line[i]} ")            
            f.write(f"\n")